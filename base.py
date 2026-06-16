import json
import re
import copy
from playwright.sync_api import sync_playwright


def fetch_more_children(page, link_id, children_ids):
    chunk_size = 30
    all_fetched_children = []

    for i in range(0, len(children_ids), chunk_size):
        chunk = children_ids[i:i + chunk_size]
        children_str = ",".join(chunk)

        api_relative_path = "/api/morechildren"

        xhr_payload_script = f"""
            async () => {{
                return new Promise((resolve, reject) => {{
                    const xhr = new XMLHttpRequest();
                    xhr.open('POST', '{api_relative_path}', true);
                    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
                    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

                    xhr.onload = function() {{
                        if (xhr.status >= 200 && xhr.status < 300) {{
                            resolve(xhr.responseText);
                        }} else {{
                            reject('HTTP Status Error: ' + xhr.status);
                        }}
                    }};

                    xhr.onerror = function() {{
                        reject('Content Security Policy Block');
                    }};

                    const params = new URLSearchParams();
                    params.append('link_id', '{link_id}');
                    params.append('children', '{children_str}');
                    params.append('api_type', 'json');

                    xhr.send(params.toString());
                }});
            }}
        """

        try:
            raw_response = page.evaluate(xhr_payload_script)
            res_json = json.loads(raw_response)

            things = []
            if isinstance(res_json, dict):
                things = res_json.get('json', {}).get('data', {}).get('things', [])
            elif isinstance(res_json, list):
                for item in res_json:
                    if isinstance(item, dict):
                        things.extend(item.get('json', {}).get('data', {}).get('things', []))

            all_fetched_children.extend(things)
            page.wait_for_timeout(350)

        except Exception as e:
            print(f"Error expanding hidden reply chunk: {e}")
            continue

    return all_fetched_children


def build_nested_tree_robust(comment_map, root_link_id):
    nodes_dict = {}
    root_comments = []

    for c_id, raw_node in comment_map.items():
        nodes_dict[c_id] = {
            'author': raw_node['author'],
            'id': c_id,
            'body': raw_node['body'],
            'score': raw_node['score'],
            'depth': 0,
            'replies': [],
            '_parent_id': raw_node['_parent_id']
        }

    for c_id, node in nodes_dict.items():
        pid = node['_parent_id']

        parent_clean_id = pid[3:] if pid and pid.startswith("t1_") else None

        if parent_clean_id and parent_clean_id in nodes_dict:
            nodes_dict[parent_clean_id]['replies'].append(node)
        else:
            root_comments.append(node)

    root_comments.sort(key=lambda x: x['id'])

    def calculate_depth_recursively(nodes_list, current_depth):
        for node in nodes_list:
            node['depth'] = current_depth
            if node['replies']:
                node['replies'].sort(key=lambda x: x['id'])  # Sort replies deterministically
                calculate_depth_recursively(node['replies'], current_depth + 1)

    calculate_depth_recursively(root_comments, 0)
    return root_comments


def fetch_thread(url):
    if "/comment/" in url:
        url = url.split("/comment/")[0]
    if url.endswith(".json"):
        url = url.replace(".json", "")

    json_target_url = re.sub(r'/$', '', url) + ".json?limit=500&threaded=true"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

        print(f"Loading hidden web view context to bypass verification gates...")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        print("Executing initial payload data layer extraction...")
        try:
            response = page.request.get(json_target_url, headers={"Referer": url})
            data = response.json()
        except Exception as e:
            browser.close()
            raise Exception(f"Failed initial data layer pass: {e}")

        if isinstance(data, list) and len(data) >= 2:
            post_listing = data[0]
            comments_listing = data[1]
        else:
            post_listing = data
            comments_listing = data

        try:
            link_id = post_listing['data']['children'][0]['data']['name']
        except (KeyError, IndexError):
            link_id = comments_listing.get('data', {}).get('children', [{}])[0].get('data', {}).get('link_id')

        if not link_id:
            browser.close()
            raise Exception("Could not isolate the core thread submission identifier.")

        comment_map = {}
        more_nodes_queue = []
        processed_more_ids = set()

        def process_raw_nodes(nodes_list):
            for node in nodes_list:
                kind = node.get('kind')
                node_data = node.get('data', {})

                if kind == 't1':
                    c_id = node_data.get('id')
                    if c_id and c_id not in comment_map:
                        comment_map[c_id] = {
                            'author': node_data.get('author', '[deleted]'),
                            'id': c_id,
                            'body': node_data.get('body', ''),
                            'score': node_data.get('score', 0),
                            '_parent_id': node_data.get('parent_id')
                        }
                    replies_block = node_data.get('replies')
                    if replies_block and isinstance(replies_block, dict):
                        process_raw_nodes(replies_block.get('data', {}).get('children', []))

                elif kind == 'more':
                    children_ids = node_data.get('children', [])
                    for child_id in children_ids:
                        if child_id not in processed_more_ids:
                            more_nodes_queue.append(child_id)
                            processed_more_ids.add(child_id)

        initial_children = comments_listing.get('data', {}).get('children', [])
        process_raw_nodes(initial_children)

        if more_nodes_queue:
            print(" Uncovering hidden sub-branches...")
            while more_nodes_queue:
                current_batch = more_nodes_queue.copy()
                more_nodes_queue.clear()

                print(f"   Expanding {len(current_batch)} deep comment branches...")
                expanded_nodes = fetch_more_children(page, link_id, current_batch)

                if not expanded_nodes:
                    break

                process_raw_nodes(expanded_nodes)

        browser.close()

        print("\n[DEBUG] Pre-Tree Assembly Status Check:")
        print(f"    Total comments captured in flat map: {len(comment_map)}")

        print("\nReassembling flat data map into hierarchical tree branches...")
        final_tree = build_nested_tree_robust(comment_map, root_link_id=link_id)
        return final_tree


def clean_comments(raw_comments):
    cleaned = []
    if not raw_comments:
        return cleaned

    for comment in raw_comments:
        cleaned_comment = copy.deepcopy(comment)
        body = cleaned_comment.get('body', '').strip()
        author = cleaned_comment.get('author', '[deleted]')

        if author == "AutoModerator":
            continue

        if body in ["[deleted]", "[removed]"]:
            cleaned_comment['body'] = "[Content removed by user or moderator]"

        if 'replies' in cleaned_comment and cleaned_comment['replies']:
            cleaned_comment['replies'] = clean_comments(cleaned_comment['replies'])

        cleaned.append(cleaned_comment)
    return cleaned


def save_comments(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def count_comments(comments_list):
    total_comments = len(comments_list)
    total_replies = 0
    for comment in comments_list:
        if 'replies' in comment and comment['replies']:
            sub_comments, sub_replies = count_comments(comment['replies'])
            total_replies += sub_comments + sub_replies
    return total_comments, total_replies


def extract_all_ids_recursively(comments_list):
    collected_ids = []
    if not comments_list:
        return collected_ids

    for comment in comments_list:
        if isinstance(comment, dict) and 'id' in comment:
            collected_ids.append(comment['id'])
            if 'replies' in comment and comment['replies']:
                collected_ids.extend(extract_all_ids_recursively(comment['replies']))
    return collected_ids


if __name__ == "__main__":
    url = input("Enter the Full Reddit URL(with https): ")

    print("=" * 80)
    print("ARGUS ENGINE v2.6 — PRODUCTION VERIFIED DEEP EXTRACTOR")
    print("=" * 80)

    print("\n Fetching entire post thread...")
    raw_comments = fetch_thread(url)
    print(f" Fetched {len(raw_comments)} top-level root branches")

    raw_c, raw_r = count_comments(raw_comments)
    print(f" RAW TOTAL RETRIEVED (Before Cleaning Filters): {raw_c + raw_r}")

    print("\n Cleaning comments...")
    cleaned = clean_comments(raw_comments)
    print(f"✓ Cleaned down to {len(cleaned)} root branches")

    print("\n Counting total comments and nested replies...")
    c, r = count_comments(cleaned)
    print(f" Total top-level root sections: {c}")
    print(f" Total nested replies (all depths): {r}")
    print(f" Grand Total Saved: {c + r}")

    print("\n Saving to JSON...")
    save_comments(cleaned, "thread_comments.json")
    print(f" Saved fully nested structure to thread_comments.json")

    print("\n Running Integrity & Duplicate Audits...")
    all_extracted_ids = extract_all_ids_recursively(cleaned)
    total_ids = len(all_extracted_ids)
    unique_ids = len(set(all_extracted_ids))

    print(f"Total ID count processed: {total_ids}")
    print(f"Unique ID count verified: {unique_ids}")

    if total_ids == unique_ids:
        print("DATA INTEGRITY VERIFIED: Zero duplicate comments across all nesting tree branches!")
    else:
        duplicates_count = total_ids - unique_ids
        print(f"WARNING: Detected {duplicates_count} duplicate elements inside the nested trees.")

    print("\n" + "=" * 80)
    print("DONE! Check thread_comments.json")
    print("=" * 80)

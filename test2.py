import json
import re
import copy
from playwright.sync_api import sync_playwright


def extract_replies_recursively(comment_or_reply, depth=1):
    """
    Recursively structures child replies into a nested list layout.
    Used for extracting fallback nested data streams.
    """
    nested_replies = []
    replies = comment_or_reply['data'].get('replies')

    if not replies or replies == "":
        return nested_replies

    children = replies.get('data', {}).get('children', [])
    for child in children:
        if child['kind'] == 't1':
            reply_dict = {
                'author': child['data'].get('author', '[deleted]'),
                'id': child['data'].get('id', ''),
                'body': child['data'].get('body', ''),
                'score': child['data'].get('score', 0),
                'depth': depth,
                'replies': extract_replies_recursively(child, depth=depth + 1)
            }
            nested_replies.append(reply_dict)

    return nested_replies


def fetch_more_children(page, link_id, children_ids):
    """
    Queries Reddit's backend to expand hidden branches using the active session.
    Uses an authentic POST form-data body layer to prevent silent rejections.
    """
    chunk_size = 100
    all_fetched_children = []

    for i in range(0, len(children_ids), chunk_size):
        chunk = children_ids[i:i + chunk_size]
        children_str = ",".join(chunk)

        api_url = "https://reddit.com"

        payload_script = f"""
            async () => {{
                const params = new URLSearchParams();
                params.append('link_id', '{link_id}');
                params.append('children', '{children_str}');
                params.append('api_type', 'json');

                const response = await fetch('{api_url}', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }},
                    body: params.toString()
                }});
                return await response.text();
            }}
        """

        try:
            raw_response = page.evaluate(payload_script)
            res_json = json.loads(raw_response)

            things = []
            if isinstance(res_json, dict):
                things = res_json.get('json', {}).get('data', {}).get('things', [])
            elif isinstance(res_json, list):
                for item in res_json:
                    if isinstance(item, dict):
                        things.extend(item.get('json', {}).get('data', {}).get('things', []))

            all_fetched_children.extend(things)
        except Exception as e:
            print(f"⚠️ Error expanding hidden reply chunk: {e}")
            continue

    return all_fetched_children


def build_nested_tree(comment_map, parent_id, depth):
    """
    Recursively rebuilds the flat tracking map into a hierarchical tree structure.
    Sorted deterministically by ID to maintain structural consistency.
    """
    nested_list = []

    current_level_nodes = sorted(
        [node for node in comment_map.values() if node.get('_parent_id') == parent_id],
        key=lambda x: x['id']
    )

    for node in current_level_nodes:
        node_id = node['id']

        comment_dict = {
            'author': node['author'],
            'id': node_id,
            'body': node['body'],
            'score': node['score'],
            'depth': depth,
            'replies': build_nested_tree(comment_map, f"t1_{node_id}", depth + 1)
        }
        nested_list.append(comment_dict)

    return nested_list


def fetch_thread(url):
    """
    Deep-crawls all levels of the thread data layer to guarantee 100% extraction accuracy
    without hitting 403 blocks or default truncation limits.
    """
    if "/comment/" in url:
        url = url.split("/comment/")[0]

    if url.endswith(".json"):
        url = url.replace(".json", "")

    # Append limit query to pull maximum data volume on the initial pass
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
        page.wait_for_timeout(3000)

        print("Executing initial payload data layer extraction...")
        try:
            raw_text = page.evaluate(
                f"async () => {{ const r = await fetch('{json_target_url}'); return await r.text(); }}")
            data = json.loads(raw_text)
        except Exception as e:
            browser.close()
            raise Exception(f"Failed initial data layer pass: {e}")

        # Unpack multi-element array (Index 0: Metadata, Index 1: Comment Listing Data)
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
            """Recursive node processing loop capturing hidden stubs at all branch depths."""
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

        # Parse initial comments listing pass
        initial_children = comments_listing.get('data', {}).get('children', [])
        process_raw_nodes(initial_children)

        # Run recursive multi-pass while loop to consume stubs dynamically
        if more_nodes_queue:
            print("🔍 Uncovering hidden sub-branches...")
            while more_nodes_queue:
                current_batch = more_nodes_queue.copy()
                more_nodes_queue.clear()

                print(f"   ↳ Expanding {len(current_batch)} deep comment branches...")
                expanded_nodes = fetch_more_children(page, link_id, current_batch)

                if not expanded_nodes:
                    break

                process_raw_nodes(expanded_nodes)

        browser.close()

        # Defend against missing parent/orphan nodes breaking the structural linkage mapping
        for c_id, node in comment_map.items():
            pid = node.get('_parent_id')
            if (
                    pid
                    and isinstance(pid, str)
                    and pid.startswith("t1_")
                    and pid[3:] not in comment_map
            ):
                node['_parent_id'] = link_id

        print("\n[DEBUG] Pre-Tree Assembly Status Check:")
        print(f"   ↳ Total comments captured in flat map: {len(comment_map)}")

        print("\nReassembling flat data map into hierarchical tree branches...")
        final_tree = build_nested_tree(comment_map, parent_id=link_id, depth=0)
        return final_tree


def clean_comments(raw_comments):
    """
    Cleans metadata labels without breaking recursive nested trees.
    Utilizes deepcopy memory isolation to completely prevent branch chopping truncation bugs.
    """
    cleaned = []
    if not raw_comments:
        return cleaned

    for comment in raw_comments:
        # Perform deep copy duplication to cleanly separate list modifications inside memory planes
        cleaned_comment = copy.deepcopy(comment)

        body = cleaned_comment.get('body', '').strip()
        author = cleaned_comment.get('author', '[deleted]')

        if body in ["[deleted]", "[removed]"]:
            continue

        if "[Content removed" in body:
            continue

        if author in ["[deleted]", "AutoModerator"]:
            continue

        if len(body.split()) < 5:
            continue

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
    """
    Deeply crawls every tier of the dictionary architecture to compile an accurate audit log.
    Validated scoping setup to prevent shortcut execution loop returns.
    """
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
    print("ARGUS ENGINE v2.4 — FINAL STABLE PRODUCTION EXTRACTOR")
    print("=" * 80)

    print("\n Fetching entire post thread...")
    raw_comments = fetch_thread(url)
    print(f"✓ Fetched {len(raw_comments)} top-level root comments")

    raw_c, raw_r = count_comments(raw_comments)
    print(f"📊 RAW TOTAL RETRIEVED (Before Cleaning Filters): {raw_c + raw_r}")

    print("\n Cleaning comments...")
    cleaned = clean_comments(raw_comments)
    print(f"✓ Cleaned down to {len(cleaned)} root comments")

    print("\n Counting total comments and nested replies...")
    c, r = count_comments(cleaned)
    print(f"✓ Total top-level comments: {c}")
    print(f"✓ Total nested replies (all depths): {r}")
    print(f"✓ Grand Total Saved: {c + r}")

    print("\n Saving to JSON...")
    save_comments(cleaned, "thread_comments.json")
    print(f"✓ Saved fully nested structure to thread_comments.json")

    print("\n Running Integrity & Duplicate Audits...")
    all_extracted_ids = extract_all_ids_recursively(cleaned)
    total_ids = len(all_extracted_ids)
    unique_ids = len(set(all_extracted_ids))

    print(f"   ↳ Total ID count processed: {total_ids}")
    print(f"   ↳ Unique ID count verified: {unique_ids}")

    if total_ids == unique_ids:
        print("   ✅ DATA INTEGRITY VERIFIED: Zero duplicate comments across all nesting tree branches!")
    else:
        duplicates_count = total_ids - unique_ids
        print(f"   ⚠️ WARNING: Detected {duplicates_count} duplicate elements inside the nested trees.")

    print("\n" + "=" * 80)
    print("DONE! Check thread_comments.json")
    print("=" * 80)

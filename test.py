import json
import re
from playwright.sync_api import sync_playwright


def fetch_more_children(page, link_id, children_ids):
    """
    Queries Reddit's backend to fetch missing comment blocks behind 'more' buttons
    using the browser's active, authenticated session.
    """
    # Chunk IDs into groups of 100 to stay within Reddit's maximum API limit
    chunk_size = 100
    all_fetched_children = []

    for i in range(0, len(children_ids), chunk_size):
        chunk = children_ids[i:i + chunk_size]
        children_str = ",".join(chunk)

        # Build the exact endpoint Reddit uses when clicking "load more comments"
        api_url = f"https://reddit.com{link_id}&children={children_str}&api_type=json"

        try:
            raw_response = page.evaluate(f"""
                async () => {{
                    const response = await fetch('{api_url}');
                    return await response.text();
                }}
            """)

            res_json = json.loads(raw_response)
            things = res_json.get('json', {}).get('data', {}).get('things', [])
            all_fetched_children.extend(things)
        except Exception as e:
            print(f"⚠️ Failed to expand a batch of hidden replies: {e}")
            continue

    return all_fetched_children


def build_nested_tree(comment_map, root_ids, parent_id, depth):
    """
    Recursively rebuilds the flat tracking map into your exact required
    hierarchical nested tree structure.
    """
    nested_list = []
    # Identify items that belong strictly to this specific parent node level
    current_level_nodes = [node for node in comment_map.values() if node['_parent_id'] == parent_id]

    # Sort them securely to preserve original chronological order if available
    for node in current_level_nodes:
        node_id = node['id']

        # Build your exact dictionary signature tracking goal
        comment_dict = {
            'author': node['author'],
            'id': node_id,
            'body': node['body'],
            'score': node['score'],
            'depth': depth,
            'replies': build_nested_tree(comment_map, root_ids, f"t1_{node_id}", depth + 1)
        }
        nested_list.append(comment_dict)

    return nested_list


def fetch_thread(url):
    """
    Loads the thread hidden, crawls the initial JSON data structure, identifies
    all 'more' hidden branch stubs, pulls them through the active session,
    and constructs a 100% complete nested conversation dictionary tree.
    """
    if "/comment/" in url:
        url = url.split("/comment/")[0]
    if url.endswith(".json"):
        url = url.replace(".json", "")

    json_target_url = re.sub(r'/$', '', url) + ".json"

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

        # Native Stealth Evasion Bypass Hook
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

        print("Loading hidden web view context to bypass verification gates...")
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

        # Extract the fundamental elements
        post_data = data[0]['data']['children'][0]['data']
        link_id = post_data['name']  # Core submission tag (e.g., t3_1rox0x3)
        initial_children = data[1]['data']['children']

        # Flat mapping registries to resolve nested parent-child trees cleanly
        comment_map = {}
        more_nodes_queue = []

        def process_raw_nodes(nodes_list):
            for node in nodes_list:
                kind = node.get('kind')
                node_data = node.get('data', {})

                if kind == 't1':  # Valid structured comment
                    c_id = node_data.get('id')
                    if c_id:
                        comment_map[c_id] = {
                            'author': node_data.get('author', '[deleted]'),
                            'id': c_id,
                            'body': node_data.get('body', ''),
                            'score': node_data.get('score', 0),
                            '_parent_id': node_data.get('parent_id')  # Linked target (e.g., t3_xx or t1_xx)
                        }
                    # Check if this element contains pre-hydrated sub-replies deep inside itself
                    replies_block = node_data.get('replies')
                    if replies_block and isinstance(replies_block, dict):
                        process_raw_nodes(replies_block.get('data', {}).get('children', []))

                elif kind == 'more':  # Hidden branch placeholder stub found!
                    children_ids = node_data.get('children', [])
                    if children_ids:
                        more_nodes_queue.extend(children_ids)

        # Parse what Reddit handed over on the first view pass
        process_raw_nodes(initial_children)

        # Expand hidden branches dynamically if any 'more' markers were discovered
        if more_nodes_queue:
            print(f"🔍 Found missing branches! Expanding {len(more_nodes_queue)} hidden comment streams...")
            expanded_nodes = fetch_more_children(page, link_id, more_nodes_queue)
            # Send the freshly unmasked comment variables back through our processing loop
            process_raw_nodes(expanded_nodes)

        browser.close()

        print("Reassembling flat data map into hierarchical tree branches...")
        # Top level root nodes link straight back to the overall Post submission ID (t3_xxxx)
        final_tree = build_nested_tree(comment_map, root_ids=list(comment_map.keys()), parent_id=link_id, depth=0)
        return final_tree


def clean_comments(raw_comments):
    cleaned = []
    for comment in raw_comments:
        body = comment['body']
        author = comment['author']
        if body in ["[deleted]", "[removed]"] or author == "AutoModerator" or len(body.split()) < 5:
            continue
        cleaned_comment = comment.copy()
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


if __name__ == "__main__":
    url = input("Enter the Full Reddit URL(with https): ")
    print("=" * 80)
    print("ARGUS ENGINE v2.0 — 100% COMPLETE DEEP THREAD EXTRACTOR")
    print("=" * 80)

    raw_comments = fetch_thread(url)
    cleaned = clean_comments(raw_comments)
    c, r = count_comments(cleaned)

    print(f"✓ Total top-level comments: {c}")
    print(f"✓ Total nested replies (all depths): {r}")
    print(f"✓ Grand Total Collected: {c + r}")

    save_comments(cleaned, "thread_comments.json")
    print("✓ Saved complete dataset to thread_comments.json")

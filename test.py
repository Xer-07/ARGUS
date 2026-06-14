import requests
import json
import time
import os
from dotenv import load_dotenv
load_dotenv()

def extract_replies_recursively(comment_or_reply, depth=0):
    all_replies = []

    replies = comment_or_reply['data']['replies']

    if replies == "":
        return all_replies

    children = replies['data']['children']

    for child in children:
        if child['kind'] == 't1':
            reply_dict = {
                'author': child['data']['author'],
                'id': child['data']['id'],
                'body': child['data']['body'],
                'score': child['data']['score'],
                'depth': depth
            }
            all_replies.append(reply_dict)
            nested_replies = extract_replies_recursively(child, depth=depth + 1)
            all_replies.extend(nested_replies)

    return all_replies



def fetch_thread(url):

    json_url = url + ".json"
    cookies = { "loid" : os.getenv("REDDIT_LOID"),"reddit_session" : os.getenv("REDDIT_SESSION")}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    response = requests.get(json_url, headers=headers, cookies=cookies, timeout=30)
    print("Status:", response.status_code)
    print(response.text[:300])
    data = response.json()
    comments = data[1]['data']['children']

    # Process comments
    comment_list = []

    for comment in comments:
        if comment['kind'] == 't1':

            author = comment['data']['author']
            id = comment['data']['id']
            body = comment['data']['body']
            score = comment['data']['score']


            # Create comment dict
            comment_dict = {
                'author': author,
                'id': id,
                'body': body,
                'score': score,
                'depth': 0,  # Top-level comments have depth 0
                'replies': extract_replies_recursively(comment, depth=1)
            }

            comment_list.append(comment_dict)

    return comment_list



def clean_comments(raw_comments):

    cleaned = []

    for comment in raw_comments:
        body = comment['body']
        author = comment['author']

        # Skip deleted/removed
        if body in ["[deleted]", "[removed]"]:
            continue

        # Skip AutoModerator
        if author == "AutoModerator":
            continue

        # Skip comments under 5 words
        if len(body.split()) < 5:
            continue

        # If this comment passes filters, keep it
        # But also clean its nested replies recursively
        cleaned_comment = comment.copy()

        if 'replies' in cleaned_comment and cleaned_comment['replies']:
            # Recursively clean nested replies
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
            replies_count, nested_count = count_comments(comment['replies'])
            total_replies += replies_count + nested_count

    return total_comments, total_replies



if __name__ == "__main__":
    # Test URL
    url = input("Enter the Full Reddit URL(with https): ")

    print("=" * 80)
    print("PHASE 1 — DATA COLLECTION — DAY 6")
    print("=" * 80)

    print("\n[1] Fetching thread...")
    raw_comments = fetch_thread(url)
    print(f"✓ Fetched {len(raw_comments)} top-level comments")

    print("\n[2] Cleaning comments...")
    cleaned = clean_comments(raw_comments)
    print(f"✓ Cleaned down to {len(cleaned)} comments")

    print("\n[3] Counting total comments and replies...")
    c, r = count_comments(cleaned)
    print(f"✓ Total top-level comments: {c}")
    print(f"✓ Total replies (all depths): {r}")

    print("\n[4] Saving to JSON...")
    save_comments(cleaned, "thread_comments.json")
    print(f"✓ Saved to thread_comments.json")

    print("\n" + "=" * 80)
    print("DONE! Check thread_comments.json")
    print("=" * 80)

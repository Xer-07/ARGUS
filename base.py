import json

def extract_replies_recursively(comment_or_reply, depth=0):
    all_replies = []
    replies = comment_or_reply["data"]["replies"]
    if replies == "":
        return all_replies
    children = replies["data"]["children"]
    for child in children:
        if child["kind"] == "t1":
            reply_dict = {
                "author": child["data"]["author"],
                "id": child["data"]["id"],
                "body": child["data"]["body"],
                "score": child["data"]["score"],
                "depth": depth,
            }
            all_replies.append(reply_dict)
            nested_replies = extract_replies_recursively(
                child,
                depth=depth + 1
            )
            all_replies.extend(nested_replies)
    return all_replies


def fetch_thread(filepath="raw_thread.json"):
    print(f"Loading Reddit data from: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(
            "Expected Reddit JSON to be a list "
            "[post_data, comments_data]"
        )
    if len(data) < 2:
        raise ValueError(
            "Invalid Reddit thread JSON structure."
        )
    comments = data[1]["data"]["children"]
    comment_list = []
    for comment in comments:
        if comment["kind"] != "t1":
            continue
        comment_dict = {
            "author": comment["data"]["author"],
            "id": comment["data"]["id"],
            "body": comment["data"]["body"],
            "score": comment["data"]["score"],
            "depth": 0,
            "replies": extract_replies_recursively(
                comment,
                depth=1
            ),
        }
        comment_list.append(comment_dict)
    return comment_list


def clean_comments(raw_comments):
    cleaned = []
    for comment in raw_comments:
        body = comment["body"]
        author = comment["author"]

        if body in ["[deleted]", "[removed]"]:
            continue

        if author == "AutoModerator":
            continue

        if len(body.split()) < 5:
            continue

        cleaned_comment = comment.copy()
        if (
            "replies" in cleaned_comment
            and cleaned_comment["replies"]
        ):
            cleaned_comment["replies"] = clean_comments(
                cleaned_comment["replies"]
            )
        cleaned.append(cleaned_comment)
    return cleaned


def save_comments(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


def count_comments(comments_list):
    total_comments = len(comments_list)
    total_replies = 0
    for comment in comments_list:
        if (
            "replies" in comment
            and comment["replies"]
        ):
            replies_count, nested_count = count_comments(
                comment["replies"]
            )
            total_replies += (
                replies_count + nested_count
            )
    return total_comments, total_replies


if __name__ == "__main__":

    print("=" * 80)
    print("PHASE 1 — DATA COLLECTION — DAY 6")
    print("=" * 80)

    print("\n[1] Loading Reddit thread...")

    raw_comments = fetch_thread(
        "raw_thread.json"
    )

    print(
        f"✓ Extracted "
        f"{len(raw_comments)} top-level comments"
    )

    print("\n[2] Cleaning comments...")

    cleaned = clean_comments(raw_comments)

    print(
        f"✓ Cleaned down to "
        f"{len(cleaned)} comments"
    )

    print("\n[3] Counting comments and replies...")

    c, r = count_comments(cleaned)

    print(f"✓ Total top-level comments: {c}")
    print(f"✓ Total replies (all depths): {r}")

    print("\n[4] Saving processed data...")

    save_comments(
        cleaned,
        "thread_comments.json"
    )

    print(
        "✓ Saved to thread_comments.json"
    )

    print("\n" + "=" * 80)
    print("DONE!")
    print("=" * 80)
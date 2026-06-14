# utils.py
def extract_comments(comment, all_comments):
    all_comments.append(comment)
    for reply in comment.get('replies', []):
        extract_comments(reply, all_comments)
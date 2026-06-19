# utils.py
def extract_comments(comment, all_comments):
    flat_comment = {k: v for k, v in comment.items() if k != 'replies'}
    all_comments.append(flat_comment)
    for reply in comment.get('replies', []):
        extract_comments(reply, all_comments)

import json
with open("thread_embeddings.json", 'r', encoding='utf-8') as f:
    comments = json.load(f)

all_comments = []

def extract_comments(comment):
    all_comments.append(comment)
    for reply in comment.get('replies', []):
        extract_comments(reply)

for comment in comments:
        extract_comments(comment)

def calculate_influence(comment):
    score = comment['score']
    reply_count = len(comment.get('replies', []))
    depth = comment['depth']
    depth_penalty = 1/(depth+1)

    influence = (score * 0.4) + (reply_count * 0.3) + (depth_penalty * 0.3)
    comment['influence'] = influence

for comment in all_comments:
    calculate_influence(comment)

srt_comm = sorted(all_comments, key = lambda x: x['influence'], reverse = True)

for comment in srt_comm[:5]:
    print(comment['influence'], "----->", comment['body'])

with open("thread_influence.json", 'w', encoding='utf-8') as f:
    json.dump(comments, f, ensure_ascii=False, indent=4)
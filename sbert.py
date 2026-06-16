import numpy as np
from sentence_transformers import SentenceTransformer
import json


def attach_embeddings(comments, model):
    for comment in comments:
        comment['embedding'] = model.encode(comment['body']).tolist()
        if comment.get('replies'):
            attach_embeddings(comment['replies'], model)  # recurse on the replies LIST
    return comments

if __name__ == "__main__":
    model = SentenceTransformer("all-MiniLM-L6-v2", cache_folder=r"C:\Ganesh\hf_cache")
    with open("thread_comments.json", encoding="utf-8") as f:
        comments = json.load(f)
    result = attach_embeddings(comments, model)
    print(result[0]['embedding'][:5])
    with open("thread_embeddings.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)


import json
import numpy as np
from sklearn.cluster import KMeans

with open("thread_embeddings.json", 'r', encoding='utf-8') as f:
    comments = json.load(f)

all_comments = []

def extract_comments(comment):
    all_comments.append(comment)
    for reply in comment.get('replies', []):
        extract_comments(reply)

for comment in comments:
        extract_comments(comment)

embeddings = np.array([comment['embedding'] for comment in all_comments])
inertias = []

k_range = range(2, 10)
for k in k_range:
    kmeans = KMeans(n_clusters=k, random_state=42).fit(embeddings)
    inertias.append(kmeans.inertia_)

drops = [inertias[i] - inertias[i+1] for i in range(len(inertias)-1)]
best_k = k_range[drops.index(max(drops)) + 1]

kmeans = KMeans(best_k, random_state=42).fit(embeddings)

for i, comment in enumerate(all_comments):
    comment['cluster'] = int(kmeans.labels_[i])

for i in range(best_k):
    print(f"\n--- Cluster {i} ---")
    for comment in all_comments:
        if comment['cluster'] == i:
            print(comment['body'][:100])

with open("thread_kmeans.json", 'w', encoding='utf-8') as f:
    json.dump(all_comments, f)
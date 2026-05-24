import json
import numpy as np
from sklearn.cluster import KMeans

# Load
with open("thread_embeddings.json", 'r', encoding='utf-8') as f:
    comments = json.load(f)

# Flatten
all_comments = []
def extract_comments(comment):
    all_comments.append(comment)
    for reply in comment.get('replies', []):
        extract_comments(reply)

for comment in comments:
    extract_comments(comment)

#KMeans
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

#Influence

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
    json.dump(all_comments, f, ensure_ascii=False, indent=4)

#Representative
def get_representative(cluster):
    rep = max(cluster, key=lambda c: c['influence'])
    return rep
for cluster_id in range(best_k):
    cluster = [c for c in all_comments if c['cluster'] == cluster_id]
    rep = get_representative(cluster)
    print(f"\nCluster {cluster_id} representative:")
    print(rep['body'][:150])

# Save
with open("thread_final.json", 'w', encoding='utf-8') as f:
    json.dump(all_comments, f, ensure_ascii=False, indent=4)


import json
from dotenv import load_dotenv
import os
print(os.getlogin())
print(os.path.expanduser("~"))
os.environ["HF_HOME"] = r"C:\Ganesh\hf_cache"
os.environ["HUGGINGFACE_HUB_CACHE"] = r"C:\Ganesh\hf_cache"
import numpy as np
from sklearn.cluster import KMeans
import json as json_parser
from groq import Groq
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
model = SentenceTransformer(
    "all-MiniLM-L6-v2",
    cache_folder=r"C:\Ganesh\hf_cache"
)

with open("thread_final.json", 'r', encoding='utf-8') as f:
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

def get_representative(cluster):
    rep = max(cluster, key=lambda c: c['influence'])
    return rep
representatives = []
cluster_stats = []
for cluster_id in range(best_k):
    cluster = [c for c in all_comments if c['cluster'] == cluster_id]
    rep = get_representative(cluster)
    representatives.append(rep)
    cluster_stats.append({"cluster_id": cluster_id, "size": len(cluster), "total_influence": sum(c['influence'] for c in cluster) ,  "avg_influence" : np.mean([c['influence'] for c in cluster]), "representative": get_representative(cluster)["body"][:200]})
dominant_cluster = max(cluster_stats, key=lambda x: x["total_influence"])["cluster_id"]

def build_prompt(nodes, all_comments, cluster_stats, dominant_cluster):
    total = len(all_comments)
    max_inf = max(c['influence'] for c in all_comments)
    avg_inf = sum(c['influence'] for c in all_comments) / total

    prompt = "You are ARGUS — a graph-based argument analysis system. Speak as an analyst reporting graph findings, not as someone reading comments.\n\n"

    prompt += f"THREAD STATISTICS:\n"
    prompt += f"- Total comments analyzed: {total}\n"
    prompt += f"- Max influence score: {max_inf:.2f}\n"
    prompt += f"- Average influence score: {avg_inf:.2f}\n"
    prompt += f"- Distinct argument clusters: {len(nodes)}\n\n"

    prompt += "CLUSTER REPRESENTATIVES (highest influence node per cluster):\n\n"

    for stat in cluster_stats:
        prompt += f"[Cluster {stat['cluster_id']}] Size: {stat['size']} | "
        prompt += f"Total Influence: {stat['total_influence']:.2f} | "
        prompt += f"Avg Influence: {stat['avg_influence']:.2f}\n"
        prompt += f"Representative: {stat['representative']}\n\n"
    prompt += f"""
GRAPH-COMPUTED DOMINANT CLUSTER: {dominant_cluster} (do not override this)\n\n"
TASK: Generate a structured Thread Verdict as a JSON object only. No prose before or after. No markdown.

Reasoning requirements before writing the verdict:
- Which cluster holds the dominant influence? Is it significantly higher than others?
- Are clusters arguing opposing positions or parallel ones?
- Is there a clear winner in the discourse, or genuine division?
- What is the structural shape of this conversation — consensus, bipolar split, fragmented, or one-sided?

Return exactly this JSON:
{{
  "verdict": "2-3 sentence analytical summary grounded in influence scores and cluster structure",
  "dominant_cluster": {dominant_cluster},
  "structural_shape": "consensus | bipolar_split | fragmented | one_sided",
  "key_arguments": ["claim from cluster X", "claim from cluster Y", "claim from cluster Z"],
  "confidence": "high | medium | low"
}}"""

    return prompt


def get_top_nodes(all_comments, n = 10):
    srt_comm = sorted(all_comments, key=lambda x: x['influence'], reverse=True)
    top = []
    for com in srt_comm[:n]:
        top.append({"body":com['body'], "influence":com['influence'], "cluster":com['cluster'], "author": com['author']})
    return top

def generate_verdict(all_comments, representatives):
    if len(all_comments) > 100:
        nodes = get_top_nodes(all_comments, n=10)
    else:
        nodes = representatives
    prompt = build_prompt(nodes, all_comments, cluster_stats, dominant_cluster)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.choices[0].message.content
    try:
        result = json_parser.loads(raw)
        print(json_parser.dumps(result, indent=2))
    except json_parser.JSONDecodeError:
        print("LLM didn't return valid JSON. Raw output:")
        print(raw)


generate_verdict(all_comments, representatives)

def query_thread(question, all_comments, top_k=5):
    embed_q = model.encode(question).tolist()
    embeddings = np.array([comment['embedding'] for comment in all_comments])
    scores = cosine_similarity([embed_q], embeddings)[0]
    top_indices = np.argsort(-scores)[:top_k]
    results = []
    for i in top_indices:
        results.append({
            "body": all_comments[i]['body'],
            "author": all_comments[i]['author'],
            "influence": all_comments[i]['influence'],
            "similarity": float(scores[i])
        })
    return results

results = query_thread("will AI replace software jobs?", all_comments)
for r in results:
    print(r)
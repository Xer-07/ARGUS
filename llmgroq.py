import json
from dotenv import load_dotenv
import os
os.environ["HF_HOME"] = r"C:\Ganesh\hf_cache"
os.environ["HUGGINGFACE_HUB_CACHE"] = r"C:\Ganesh\hf_cache"
import numpy as np
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

def generate_verdict(all_comments, representatives, cluster_stats, dominant_cluster):
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
        return result
    except json_parser.JSONDecodeError:
        return {"error": "LLM returned invalid JSON", "raw": raw}

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

if __name__ == "__main__":
    from pipeline import cluster_and_score

    with open("thread_final.json", 'r', encoding='utf-8') as f:
        all_comments = json.load(f)  # already flat — no extract_comments needed

    all_comments, cluster_stats, dominant_cluster, representatives = cluster_and_score(all_comments)
    verdict = generate_verdict(all_comments, representatives, cluster_stats, dominant_cluster)
    print(json_parser.dumps(verdict, indent=2))

    results = query_thread("How much money was required in 1998 to live comfortably?", all_comments)
    for r in results:
        print(r)
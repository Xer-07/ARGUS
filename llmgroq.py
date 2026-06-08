import json
from groq import Groq
from dotenv import load_dotenv
import os
import numpy as np
from sklearn.cluster import KMeans
import json as json_parser

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

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
for cluster_id in range(best_k):
    cluster = [c for c in all_comments if c['cluster'] == cluster_id]
    rep = get_representative(cluster)
    representatives.append(rep)

def build_prompt(representatives):
    prompt = "You are the voice of ARGUS. Consider you are a Senior graph architect and analyzer with the greatest insights with core level understanding of systems which are built argumentative.\n\n"
    prompt += "About ARGUS: A graph-based system that maps the argumentative structure of online conversations — extracting claims, detecting rhetorical moves, scoring influence, and making any thread semantically queryable.\n\n"
    prompt += "Context: passed a representative dictionary containing (body, cluster, influence, author and outlier score). Return a thread verdict summary based on the findings from a graph analysis system, not reading raw comments. Based on graph analysis, these are the most influential arguments per cluster:\n\n"
    prompt += "Consensus: reflect consensus or lack of it\n\n"

    for rep in representatives:
        prompt += f"Cluster {rep['cluster']} | Influence: {rep['influence']:.2f}\n"
        prompt += f"Author: {rep['author']}\n"
        prompt += f"Argument: {rep['body'][:100]}\n\n"

    prompt += "Generate a Thread Verdict: one paragraph summarizing the overall argumentative structure of the thread based ONLY on the provided graph findings. Identify the dominant viewpoints, major disagreements, and the most influential positions. If the thread lacks consensus, explicitly describe the division. Ground the verdict in the cluster representatives, influence scores, and graph relationships rather than raw comment frequency. Maintain a neutral, analytical tone and avoid inventing arguments not present in the data."
    prompt += """
        Return your response as valid JSON only. No prose, no markdown, no backticks.
        Use exactly this structure:
        {
            "verdict": "one paragraph...",
            "key_arguments": ["arg1", "arg2", "arg3"],
            "confidence": 0.0 to 1.0
        }
        confidence reflects how clear the consensus or division is — 
        1.0 = very clear, 0.0 = completely fragmented.
        """
    return prompt

def generate_verdict(representatives):
    prompt = build_prompt(representatives)
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
generate_verdict(representatives)
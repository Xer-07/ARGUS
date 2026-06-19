from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from utils import extract_comments
from base import fetch_thread, clean_comments
from sbert import attach_embeddings
from pipeline import cluster_and_score
from llmgroq import generate_verdict, query_thread
import os

os.environ["HF_HOME"] = r"C:\Ganesh\hf_cache"
os.environ["HUGGINGFACE_HUB_CACHE"] = r"C:\Ganesh\hf_cache"

app = FastAPI()
model = SentenceTransformer("all-MiniLM-L6-v2", cache_folder=r"C:\Ganesh\hf_cache")

# Module-level state — Day 27 replaces this with persistent storage
last_analysis = {}

class AnalyzeRequest(BaseModel):
    url: str

class QueryRequest(BaseModel):
    question: str

@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    raw = fetch_thread(request.url)
    cleaned = clean_comments(raw)
    embedded = attach_embeddings(cleaned, model)

    all_comments = []
    for c in embedded:
        extract_comments(c, all_comments)

    all_comments, cluster_stats, dominant_cluster, representatives = cluster_and_score(all_comments)
    verdict = generate_verdict(all_comments, representatives, cluster_stats, dominant_cluster)

    last_analysis["all_comments"] = all_comments
    last_analysis["url"] = request.url

    return {
        "verdict": verdict,
        "dominant_cluster": dominant_cluster,
        "cluster_stats": cluster_stats
    }

@app.post("/query")
def query(request: QueryRequest):
    if not last_analysis:
        return {"error": "No thread analyzed yet. Call /analyze first."}

    results = query_thread(request.question, last_analysis["all_comments"], 5)
    return {"results": results}
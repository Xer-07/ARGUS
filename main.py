from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from utils import extract_comments
from base import fetch_thread, clean_comments
from sbert import attach_embeddings
from pipeline import cluster_and_score
from llmgroq import generate_verdict, query_thread
import os
from db import init_db, get_cached, save_cache
import hashlib
import json

os.environ["HF_HOME"] = r"C:\Ganesh\hf_cache"
os.environ["HUGGINGFACE_HUB_CACHE"] = r"C:\Ganesh\hf_cache"

init_db()
app = FastAPI()
model = SentenceTransformer("all-MiniLM-L6-v2", cache_folder=r"C:\Ganesh\hf_cache")

# Module-level state — Day 27 replaces this with persistent storage
last_analysis = {}

class AnalyzeRequest(BaseModel):
    url: str

class QueryRequest(BaseModel):
    question: str
    url: str

@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    url_hash = hashlib.sha256(request.url.encode()).hexdigest()

    cached = get_cached(url_hash)
    if cached:
        comments_raw, result_raw = cached
        return json.loads(result_raw)

    raw = fetch_thread(request.url)
    cleaned = clean_comments(raw)
    embedded = attach_embeddings(cleaned, model)

    all_comments = []
    for c in embedded:
        extract_comments(c, all_comments)

    all_comments, cluster_stats, dominant_cluster, representatives = cluster_and_score(all_comments)
    verdict = generate_verdict(all_comments, representatives, cluster_stats, dominant_cluster)

    result = {
        "verdict": verdict,
        "dominant_cluster": dominant_cluster,
        "cluster_stats": cluster_stats
    }

    save_cache(url_hash, request.url, json.dumps(all_comments), json.dumps(result))
    return result

@app.post("/query")
def query(request: QueryRequest):
    url_hash = hashlib.sha256(request.url.encode()).hexdigest()

    cached = get_cached(url_hash)
    if not cached:
        return {"error": "Thread not analyzed yet. Call /analyze first."}

    comments_raw, _ = cached
    all_comments = json.loads(comments_raw)

    results = query_thread(request.question, all_comments, model, 5)
    return {"results": results}
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from utils import extract_comments
from base import fetch_thread, clean_comments
from sbert import attach_embeddings
from pipeline import cluster_and_score
from graph import query_graph
from llmgroq import generate_verdict, query_thread
import os
from db import init_db, get_cached, save_cache
import hashlib
import json
from neo4j import GraphDatabase

from dotenv import load_dotenv
load_dotenv()

os.environ["HF_HOME"] = r"C:\Ganesh\hf_cache"
os.environ["HUGGINGFACE_HUB_CACHE"] = r"C:\Ganesh\hf_cache"

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD'))
)


init_db()
app = FastAPI()
model = SentenceTransformer("all-MiniLM-L6-v2", cache_folder=r"C:\Ganesh\hf_cache")


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

    all_comments, cluster_stats, dominant_cluster, representatives, outlier = cluster_and_score(all_comments)
    verdict = generate_verdict(all_comments, representatives, cluster_stats, dominant_cluster)

    result = {
        "verdict": verdict,
        "dominant_cluster": dominant_cluster,
        "cluster_stats": cluster_stats,
        "outlier": {
            "body": outlier['body'],
            "author": outlier['author'],
            "outlier_score": outlier['outlier_score']
        }
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

@app.post("/graph")
def graph(request: AnalyzeRequest):
    url_hash = hashlib.sha256(request.url.encode()).hexdigest()
    cached = get_cached(url_hash)
    if not cached:
        return {"error": "Thread not analyzed yet. Call /analyze first."}

    comments_raw, _ = cached
    all_comments = json.loads(comments_raw)
    ids = [c['id'] for c in all_comments]
    records = query_graph(ids, driver)

    nodes = {}
    edges = []

    for record in records:
        if record["a.id"] not in nodes:
            nodes[record["a.id"]] = {
                "id": record["a.id"],
                "author": record["a.author"],
                "influence": record["a.influence"],
                "cluster": record["a.cluster"],
                "body": record["a.body"]
            }
        if record["b.id"] not in nodes:
            nodes[record["b.id"]] = {
                "id": record["b.id"],
                "author": record["b.author"],
                "influence": record["b.influence"],
                "cluster": record["b.cluster"],
                "body": record["b.body"]
            }
        edges.append({
            "source": record["a.id"],
            "target": record["b.id"],
            "type": record["relationship"]
        })
    return {"nodes": list(nodes.values()), "edges": edges}

   
    

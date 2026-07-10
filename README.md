# ARGUS — Argument Graph & Understanding System

<p align="center">
  <img src="assets/banner.png" alt="ARGUS Banner" width="100%">
</p>

> Paste a Reddit URL. Get the argumentative skeleton of the entire thread in seconds.

ARGUS treats a Reddit thread not as a list of text but as a **directed argument graph** — mapping claims, influence, and semantic clusters — so you can understand 500 comments in under 2 minutes.

---

## The Core Idea

Every other Reddit summarizer feeds comments into an LLM and gets a paragraph back. The LLM decides what matters.

ARGUS builds argument structure **mathematically first** — then uses an LLM only to articulate what the graph already found.

**The graph is the brain. The LLM is just the voice.**

---

## Output (per thread)

| Feature | What it is |
|---|---|
| **Thread Verdict** | One paragraph — consensus or lack of it, grounded in influence scores |
| **Argument Clusters** | 5–7 distinct positions, each represented by the highest-influence comment from that cluster |
| **Claim Map** | Visual directed graph — which arguments support or contradict each other |
| **The Outlier** | The most semantically distant comment from all clusters — often the most interesting take |
| **Query Box** | Ask questions, get answers from the thread's graph — not LLM memory |

---

## How It Works

```
Reddit URL
    → fetch thread via .json endpoint
    → clean and filter comments
    → encode every comment as a 384-dim embedding (sentence-transformers)
    → KMeans clustering with auto-selected K (elbow method)
    → influence score per comment: (upvotes × 0.4) + (reply_count × 0.3) + (depth_penalty × 0.3)
    → representative comment per cluster (highest influence)
    → outlier detection (max average cosine distance from all centroids)
    → Neo4j graph: nodes = comments, edges = support/contradiction/extension
    → Gemini generates Thread Verdict from graph findings
    → FastAPI + Streamlit serve the result
```

---

## Tech Stack

| Layer | Tool |
|---|---|
| Data fetching | `requests` — Reddit `.json` endpoint, no API key needed |
| Embeddings | `sentence-transformers` — all-MiniLM-L6-v2 |
| Clustering | `scikit-learn` KMeans + elbow method |
| Graph DB | `Neo4j` Aura |
| LLM | `Google Gemini API` |
| Backend | `FastAPI` |
| Frontend | `Streamlit` + `pyvis` |

---

## Current Progress

**Phase 1 — Data Collection**
- [x] Fetch Reddit thread via `.json` trick (no PRAW needed)
- [x] Recursive deep reply traversal at all depths
- [x] Structure each comment: author, body, score, depth, parent
- [x] Filter deleted comments, AutoModerator, comments under 5 words
- [x] Refactored into clean functions: `fetch_thread`, `clean_comments`, `save_comments`

**Phase 2 — Embeddings + Graph Building**
- [x] Sentence-transformer embeddings on all comments and replies
- [x] KMeans clustering with automatic K selection via elbow method
- [x] Influence score calculation per comment
- [x] Representative comment selection per cluster
- [x] Outlier detection — most semantically distant comment
- [x] Neo4j graph construction
- [x] Typed edge classification (supports / contradicts / extends)

**Phase 3–6**
- [x] Gemini LLM summarization
- [x] FastAPI backend
- [ ] React frontend
- [ ] Docker + Vercel Deployment

---

## Setup

```bash
git clone https://github.com/Xer-07/Argus.git
cd Argus
pip install requests sentence-transformers scikit-learn numpy
python base.py        # Phase 1: fetch and clean
python pipeline.py    # Phase 2: embed, cluster, score, outlier
```

---

## Status

Active development — first year CSE undergrad building this as a research + portfolio project.  
Target: deployed system + undergraduate research paper.

---

*Built by Ganeshkumar V — B.Tech CSE, Amrita Vishwa Vidyapeetham*

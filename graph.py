from neo4j import GraphDatabase
from dotenv import load_dotenv
import numpy as np
import os
import json
import sys
from utils import extract_comments

load_dotenv()

URI = os.getenv('NEO4J_URI')
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

with open("thread_final.json", encoding="utf-8") as file:
    comments = json.load(file)


#-----------EXTRACT COMMENTS---------------#
all_comments = []
for comment in comments:
    extract_comments(comment, all_comments)


#-----------COMMENT NODES---------------#
def comment_nodes(driver,all_comments):
    summary = driver.execute_query(""" UNWIND $comments AS comment CREATE (c:Comment {
            author: comment.author,
            id: comment.id,
            body: comment.body,
            score: comment.score,
            depth: comment.depth,
            cluster: comment.cluster,
            influence: comment.influence})""", comments=all_comments).summary

    print("Created {nodes_created} nodes in {time} ms.".format(
        nodes_created=summary.counters.nodes_created,
        time=summary.result_available_after
    ))

comment_nodes(driver, all_comments)

#-------CLASSIFY--------------#
def classify_relationship(similarity):
    relationship = ''
    if similarity > 0.5:
        relationship = "SUPPORTS"
    elif 0.4 < similarity < 0.5:
        relationship = "EXTENDS"
    elif similarity < 0.25:
        relationship =  "CONTRADICTS"
    else:
        pass
    return relationship


#-------EDGES--------------#
def create_edge(edges):
    supports = [e for e in edges if e["type"] == "SUPPORTS"]
    contradicts = [e for e in edges if e["type"] == "CONTRADICTS"]
    extends = [e for e in edges if e["type"] == "EXTENDS"]

    summary_supp = driver.execute_query(
        """UNWIND $edges AS edge 
           MATCH (a:Comment {id: edge.source}) 
           MATCH (b:Comment {id: edge.target}) 
           CREATE (a)-[:SUPPORTS]->(b)""",
        edges=supports
    ).summary

    summary_ext = driver.execute_query(
        """UNWIND $edges AS edge 
           MATCH (a:Comment {id: edge.source}) 
           MATCH (b:Comment {id: edge.target}) 
           CREATE (a)-[:EXTENDS]->(b)""",
        edges=extends
    ).summary

    summary_cont = driver.execute_query(
        """UNWIND $edges AS edge 
           MATCH (a:Comment {id: edge.source}) 
           MATCH (b:Comment {id: edge.target}) 
           CREATE (a)-[:CONTRADICTS]->(b)""",
        edges=contradicts
    ).summary

    print(f"Created {summary_supp.counters.relationships_created} SUPPORTS edges")
    print(f"Created {summary_ext.counters.relationships_created} EXTENDS edges")
    print(f"Created {summary_cont.counters.relationships_created} CONTRADICTS edges")

#-------SIMILARITY--------------#
def cos_sim(a,b):
    return np.dot(a,b) / (np.linalg.norm(a) * np.linalg.norm(b))

edges = []
cluster_map = {}

for comment in all_comments:
    cluster_map.setdefault(comment["cluster"], []).append(comment)

for cluster_comments in cluster_map.values():
    for i in range(len(cluster_comments)):
        for j in range(i+1, len(cluster_comments)):
            sim = cos_sim(cluster_comments[i]["embedding"], cluster_comments[j]["embedding"])
            rel = classify_relationship(sim)
            if rel:
                edges.append({
                    "source": cluster_comments[i]["id"],
                    "target": cluster_comments[j]["id"],
                    "type": rel
                })

create_edge(edges)
driver.close()
sys.exit(0)
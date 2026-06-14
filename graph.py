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
def comment_nodes(driver,Comment):
    summary = driver.execute_query(""" CREATE (c:Comment {author: $author, body: $body, score: $score, depth: $depth, cluster: $cluster, influence: $influence})""", author = Comment['author'], body = Comment['body'], score = Comment['score'], depth = Comment['depth'], cluster = Comment['cluster'], influence = Comment['influence']).summary
    print("Created {nodes_created} nodes in {time} ms.".format(
        nodes_created=summary.counters.nodes_created,
        time=summary.result_available_after
    ))

for c in all_comments:
    comment_nodes(driver,c)


#-------CLASSIFY--------------#
def classify_relationship(similarity):
    relationship = ''
    if similarity > 0.7:
        relationship = "supports"
    elif similarity < 0.3:
        relationship =  "contradicts"
    else:
        pass
    return relationship


#-------EDGES--------------#
def create_edge(driver, body_a, body_b, relationship):
    driver.execute_query("""
            MATCH (a:Comment {body: $body_a})
            MATCH (b:Comment {body: $body_b})
            CREATE (a)-[:""" + relationship + """]->(b)
        """, body_a=body_a, body_b=body_b)

#-------SIMILARITY--------------#
def cos_sim(a,b):
    return np.dot(a,b) / (np.linalg.norm(a) * np.linalg.norm(b))

for i in range(len(all_comments)):
    for j in range(i+1, len(all_comments)):
        a = all_comments[i]
        b = all_comments[j]
        sim = cos_sim(np.array(a['embedding']), np.array(b['embedding']))
        rel = classify_relationship(sim)
        if rel:
            create_edge(driver, a['body'], b['body'], rel)


driver.close()
sys.exit(0)
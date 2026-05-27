from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
import json
import sys

load_dotenv()

URI = os.getenv('NEO4J_URI')
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

with open("thread_final.json", encoding="utf-8") as file:
    comments = json.load(file)
all_comments = []
def extract_comments(comment):
    all_comments.append(comment)
    for reply in comment.get('replies', []):
        extract_comments(reply)

for comment in comments:
    extract_comments(comment)

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

def comment_nodes(driver,Comment):
    summary = driver.execute_query(""" CREATE (c:Comment {author: $author, body: $body, score: $score, depth: $depth, cluster: $cluster, influence: $influence})""", author = Comment['author'], body = Comment['body'], score = Comment['score'], depth = Comment['depth'], cluster = Comment['cluster'], influence = Comment['influence']).summary
    print("Created {nodes_created} nodes in {time} ms.".format(
        nodes_created=summary.counters.nodes_created,
        time=summary.result_available_after
    ))

for c in all_comments:
    comment_nodes(driver,c)

driver.close()
sys.exit(0)
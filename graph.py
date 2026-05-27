from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

URI = os.getenv('NEO4J_URI')
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

def test_connection(driver):
    records, summary, keys = driver.execute_query("RETURN 1 AS result")
    print("Connection successful:", records[0].data())

test_connection(driver)
driver.close()
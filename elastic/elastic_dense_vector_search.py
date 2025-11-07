import os

import polars as pl

from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2", device="mps")

library = pl.read_csv("library.csv")
client = Elasticsearch(
    "http://localhost:9200",
    api_key=os.getenv("ES_LOCAL_API_KEY")
)

print("Elasticsearch Keyword Search")
print("Type 'exit' or 'quit' to stop\n")

while True:
    query = input("Enter search query: ").strip()
    if query.lower() in ['exit', 'quit', '']:
        print("Exiting...")
        break

    query_vector = model.encode(query).tolist()

    retriever_object = {
        "standard": {
            "query": {
                "knn": {
                    "field": "vector",
                    "query_vector": query_vector,
                    "k": 100,
                    "num_candidates": 100
                }
            }
        }
    }
    
    try:
        search_response = client.search(
            index="references-dv",
            retriever=retriever_object,
        )
        
        print(f"\nResults for '{query}':")
        print("-" * 50)
        keys = [hit['_source'].get('key') for hit in search_response['hits']['hits']]
        results = library.filter(pl.col('Key').is_in(keys))
        print(results.select(['Key', 'Title', 'Author', 'Date', 'Journal Abbreviation']))
        print(f"Total hits: {search_response['hits']['total']['value']}\n")
        
    except Exception as e:
        print(f"Error during search: {e}\n")

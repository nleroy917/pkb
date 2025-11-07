import os

import polars as pl

from elasticsearch import Elasticsearch


library = pl.read_csv("library.csv")
client = Elasticsearch("http://localhost:9200", api_key=os.getenv("ES_LOCAL_API_KEY"))

print("Elasticsearch Keyword Search")
print("Type 'exit' or 'quit' to stop\n")

while True:
    query = input("Enter search query: ").strip()

    if query.lower() in ["exit", "quit", ""]:
        print("Exiting...")
        break

    retriever_object = {
        "standard": {"query": {"multi_match": {"query": query, "fields": ["text"]}}}
    }

    try:
        search_response = client.search(
            index="references",
            retriever=retriever_object,
        )

        print(f"\nResults for '{query}':")
        print("-" * 50)
        keys = [hit["_source"].get("key") for hit in search_response["hits"]["hits"]]
        results = library.filter(pl.col("Key").is_in(keys))
        print(
            results.select(["Key", "Title", "Author", "Date", "Journal Abbreviation"])
        )
        print(f"Total hits: {search_response['hits']['total']['value']}\n")

    except Exception as e:
        print(f"Error during search: {e}\n")

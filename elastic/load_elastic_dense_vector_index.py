import os

import polars as pl

from elasticsearch import Elasticsearch, helpers

df = pl.read_parquet("datasets/all_minilm_l6_v2.parquet")

es = Elasticsearch(
    "http://localhost:9200",
    api_key=os.getenv("ES_LOCAL_API_KEY")
)

def load_data():
    for row in df.iter_rows(named=True):
        yield {
            "_index": "references-dv",
            "_source": {
                "vector": row["embedding"],
                "text": row["chunk_text"],
                "key": row["key"]
            }
        }

helpers.bulk(es, load_data())
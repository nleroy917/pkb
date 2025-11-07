#!/bin/bash
# note, you must source the .env file to get the ES_LOCAL_API_KEY variable
curl -X PUT 'http://localhost:9200/references-dv' --header "Authorization: ApiKey $ES_LOCAL_API_KEY" --header "Content-Type: application/json" --data-raw '{
  "mappings": {
    "properties":{
      "vector":{
        "type": "dense_vector",
        "dims": 384
      },
      "text":{
        "type": "text"
      },
      "key":{
        "type":"keyword"
      }
    }
  }
}'
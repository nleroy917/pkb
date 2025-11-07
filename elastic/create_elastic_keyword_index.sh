#!/bin/bash
# note, you must source the .env file to get the ES_LOCAL_API_KEY variable
# this creates a standard keyword index on the "text" field
curl -X PUT 'http://localhost:9200/references' --header "Authorization: ApiKey $ES_LOCAL_API_KEY" --header 'Content-Type: application/json' --data-raw '{
  "mappings": {
    "properties":{
      "text":{
        "type":"text"
      },
      "key":{
        "type":"keyword"
      }
    }
  }
}'
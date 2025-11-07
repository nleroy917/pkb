# elastic/qdrant reference document search
This repository contains code to test two different systems for searching a local database of reference documents: Elasticsearch vs. Qdrant.

The plan is to index both my personal Zotero library (academic literature) and my personal collection of markdown files in Obsidian. I want to build a small, local cli tool that allows me to quickly search through these documents using either keyword search (Elasticsearch) or vector similarity search (Elasticsearch or Qdrant).

Some example commands:
```bash
pkb index --backend elasticsearch
```
```bash
pkb search --backend qdrant --query "What are the applications of quantum computing in cryptography?"
```
The system should be able to detect when new documents are available and update the indexes accordingly. Adding generative AI capabilities (e.g., using OpenAI's GPT models) to summarize or answer questions based on the search results is a potential future enhancement as well.

Rust may be used for development since I really like their trait system (allows multiple backends and also multiple search strategies). However, initial prototyping will be done in Python for speed of development and ease of use with existing libraries.
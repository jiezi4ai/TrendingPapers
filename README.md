# TrendingPapers
Pipeline for extracting daily trending papers cater to your interests.

## Why Tending Papers
One may easily get lost in tons of recommendations and daily feeds on latest researches and papers.
This project tries to rebuild a pipeline for geting the most relevant and most important research work automatically.  
More specifically, it tries to:
1. Get papers from varies sources, including Arxiv preprints, Huggingface daily papers, Twitter posts, Githubs, etc.
2. Match papers to one's interest. Given a few keywords or one's reading list from library, daily paper would be further filtered based on semantic similarity.
3. Build with data and knowledge management idea (WIP). For example, it tries to interact with Zotero for paper management. It also leverage Sqlite for better data management. 

## Quick Start
**Set up config.py**
**Run main.py**
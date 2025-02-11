import os
from datetime import datetime, timedelta

CURRENT_DT = datetime.today().strftime('%Y-%m-%d')
YESTERDAY = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d') 

CONFIG = {
    'DEBUG': True,
    'TIME': {
        'CURRENT_DT': CURRENT_DT,
        'YESTERDAY': YESTERDAY,
        'TIMELENGTH': 7,  # datelength of past 7 days
    },
    'ARXIV':{
        'DOMAIN': ['cs', 'stat'],  # domain refer to http://export.arxiv.org/oai2?verb=ListSets
        'CATEGORY':  # category refer to https://arxiv.org/category_taxonomy
            ['cs.CV', 'cs.CL', 'cs.AI', 'cs.LG', 'cs.RO', 'cs.SI', 'cs.IR', 'stat.AP', 'stat.ML'],
    },
    'TWITTER': {
        'FOLLOWED_ACCTS': ["fly51fly",  # 爱可可
                        "rohanpaul_ai",   # tweets on ai papers often
                        "TheTuringPost",  # Turing Post from https://www.turingpost.com/
                        "dair_ai",  # ML Papers of the Week
                        "omarsar0"],  # also tweets on papers
        'DETECTED_WEBSITE': [   # detect if tweet contains following url
            'arxiv.org',
            'semanticscholar.org',
            'openreview.net',
            'researchgate.net',
        ]
    },
    'DATABASE': {  # params on database
        'DB_PATH': '/home/jiezi/Code/Github/TrendingPapers/data/',
        'DB_NAME': 'trending_papers.db',

        'OAI_PAPER_TBL_NM': "oai_paper_pool",  # table for preprint paper metadata (batch trhough OAI)
        'OAI_PAPER_TBL_KEY': 'identifier',   # PK column for OAI_PAPER_TBL_NM

        'SS_PAPER_TBL_NM': "ss_paper_pool",  # table for all papers pool (use semantic scholar format)

        'DAILY_PAPER_TBL_NM': "daily_paper_pool", # table for daily recommended / discussed /reviewed papers

        'TW_TWEET_TBL_NM': "twitter_tweets_pool",  # table to store tweets data
        'TW_TWEET_TBL_KEY': 'id_str',

        'TW_ACCT_TBL_NM': "twitter_acct_pool",   # table to store followed accts
        'TW_ACCT_TBL_KEY': 'user_id_str'
        },
    'LLM':{     # llm model settings
        'GEMINI_API_KEY': os.getenv('GEMINI_API_KEY_1'),
        'GEMINI_MDL_NM': "gemini-2.0-flash-exp"
    },
    'EMBED': {   # embedding model settings
        'EMBEDDING_MODEL': "snowflake-arctic-embed2:latest",
        'EMBEDDING_MODEL_DIM': 1024,
        'EMBEDDING_MODEL_MAX_TOKENS': 8192
    },
    'API':{  # optional apis
        'ZOTERO_LIB_ID': os.getenv('ZOTERO_LIB_ID_1'),
        'ZOTERO_API_KEY': os.getenv('ZOTERO_API_KEY_1'),
        'FIRECRAWL_API_KEY': os.getenv('FIRECRAWL_API_KEY_2'),
    }
}
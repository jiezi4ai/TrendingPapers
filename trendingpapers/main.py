import pandas as pd
from typing import List, Dict, Optional

from config import CONFIG

from .dly_preprint_papers import PapersPreprint
from .dly_discussed_papers import PapersDiscussed
from .dly_recommended_papers import PapersRecommended
from .database.sqlite_interface import df_to_sqlite
from .filter_and_ranking import filter_by_topics

async def get_dly_papers():
    """get daily preprint papers on specific domain and save to database
    """
    oai = PapersPreprint(data_path = CONFIG['DATABASE']['DB_PATH'])
    # get daily preprint papers of specific 
    preprint_papers_metadata = await oai.pull_arxiv_metadata(
        domains = CONFIG['ARXIV']['DOMAIN'],
        from_date = CONFIG['TIME']['YESTERDAY'],
        until_date = CONFIG['TIME']['CURRENT_DT'])
    
    # filter by restrict categories
    filtered_papers_metadata = oai.filter_by_category(
        paper_metadata = preprint_papers_metadata,
        categories = CONFIG['ARXIV']['CATEGORY'])
    
    # save data to database
    df = pd.DataFrame(filtered_papers_metadata)
    df['insert_dt'] = CONFIG['TIME']['CURRENT_DT']
    df_to_sqlite(
        df, 
        table_name = CONFIG['DATABASE']['OAI_PAPER_TBL_NM'], 
        db_name = CONFIG['DATABASE']['DB_PATH'] + '/' +  CONFIG['DATABASE']['DB_NAME'],
        if_exists = 'append', 
        id_key = CONFIG['DATABASE']['OAI_PAPER_TBL_KEY'])
    return filtered_papers_metadata

def get_trending_papers():
    # get recommended papers
    rec = PapersRecommended()
    github_papers_metadata = rec.get_github_recommended_papers()
    hf_papers_metadata = rec.get_huggingface_daily_papers()

    # get discussed papers from twitter
    tw = PapersDiscussed(if_proxy=True)
    followed_users, followed_tweets = tw.get_user_tweets(top_k=30)
    
    # save user information
    df_tw_accts = pd.DataFrame(followed_users)
    df_tw_accts['insert_dt'] = CONFIG['TIME']['CURRENT_DT']
    df_to_sqlite(
        df_tw_accts, 
        table_name = CONFIG['DATABASE']['TW_ACCT_TBL_NM'], 
        db_name = CONFIG['DATABASE']['DB_PATH'] + '/' +  CONFIG['DATABASE']['DB_NAME'],
        if_exists = 'append', 
        id_key = CONFIG['DATABASE']['TW_ACCT_TBL_KEY'])
    
    # save tweets information
    df_tw_tweets = pd.DataFrame(followed_tweets)
    df_tw_tweets['insert_dt'] = CONFIG['TIME']['CURRENT_DT']
    df_to_sqlite(
        df_tw_tweets, 
        table_name = CONFIG['DATABASE']['TW_TWEET_TBL_NM'], 
        db_name = CONFIG['DATABASE']['DB_PATH'] + '/' +  CONFIG['DATABASE']['DB_NAME'],
        if_exists = 'append', 
        id_key = CONFIG['DATABASE']['TW_TWEET_TBL_KEY'])
    
    # get paper related tweets
    tweet_paper_metadata, _ = tw.regroup_user_tweets(
        tweets = followed_tweets, 
        base_dt = CONFIG['TIME']['CURRENT_DT'],
        timelength = CONFIG['TIME']['TIMELENGTH'])

    # consolidate all papers
    recommended_papers_metadata = github_papers_metadata + hf_papers_metadata + tweet_paper_metadata
    # save all papers
    df_papers = pd.DataFrame(recommended_papers_metadata)
    df_papers['insert_dt'] = CONFIG['TIME']['CURRENT_DT']
    df_to_sqlite(
        df_papers, 
        table_name = CONFIG['DATABASE']['DAILY_PAPER_TBL_NM'], 
        db_name = CONFIG['DATABASE']['DB_PATH'] + '/' +  CONFIG['DATABASE']['DB_NAME'],
        if_exists = 'append')
    return recommended_papers_metadata

async def filter_and_ranking_papers(
        candidate_papers_info: List[str],
        benchmark_texts: Optional[List[str]] = None,
        if_zotero: Optional[bool] = False,
        zotero_lib_id: Optional[str] = CONFIG['API']['ZOTERO_LIB_ID'],
        zotero_api_key: Optional[str] = CONFIG['API']['ZOTERO_API_KEY']  
    ):
    """calculate semantic similarity between candidate_papers_info (from daily papers) and benchmark_texts (for user defined keywords, or user's existing papers)
    keep only alike papers
    """
    if if_zotero:
        if zotero_lib_id and zotero_api_key:
            try:
                # further 
                from pyzotero import zotero
                zot = zotero.Zotero(library_id=zotero_lib_id, library_type='user', api_key=zotero_api_key) # local=True for read access to local Zotero
                zot_papers = zot.top(limit=20, itemType='book || conferencePaper || journalArticle || preprint')  # itemType refer to zot.item_types()
                benchmarks = [x.get('data', {}).get('abstractNote') for x in zot_papers 
                              if x.get('data', {}).get('abstractNote')]
            except Exception as e:
                print(f"Could not access zotero due to {e}")
                benchmarks = []
    if benchmark_texts:
        benchmarks += benchmark_texts

    matched_papers_metadata, match_relationships  = await filter_by_topics(benchmarks, candidate_papers_info)
    return matched_papers_metadata, match_relationships

async def run_trending_papers():
    # from all daily papers
    dly_papers_metadata = await get_dly_papers()
    dly_papers_abstracts = [x.get('abstract', 'NA') for x in dly_papers_metadata]
    matched_dlypapers_metadata, match_relationships = await filter_and_ranking_papers(
        candidate_papers_info = dly_papers_abstracts, 
        if_zotero = True)

    # from recommended papers
    recommended_papers_metadata = get_trending_papers()
    rec_papers_abstracts = [x.get('abstract', 'NA') for x in recommended_papers_metadata]
    matched_recpapers_metadata, match_relationships = await filter_and_ranking_papers(
        candidate_papers_info = rec_papers_abstracts, 
        if_zotero = True)
    
    urls = [x.get('paper_url') for x in matched_dlypapers_metadata+matched_recpapers_metadata if x.get('paper_url')]
    # search semantic scholar for detailed paper metadata


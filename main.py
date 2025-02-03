import asyncio
import json
import pandas as pd
from typing import List, Dict, Optional

from trendingpapers.config import CONFIG

from trendingpapers.dly_preprint_papers import PapersPreprint
from trendingpapers.dly_discussed_papers import PapersDiscussed
from trendingpapers.dly_recommended_papers import PapersRecommended
from trendingpapers.database.sqlite_interface import df_to_sqlite
from trendingpapers.filter_and_ranking import filter_by_topics

def deduplicate_list_of_dicts(data, key):
  """dedup list of dicts based on given key. Keep only the first item.
  """
  seen = set()  # 使用集合来高效地检查是否已经遇到过某个值
  deduplicated_data = []
  for item in data:
    value = item[key]
    if value not in seen:
      seen.add(value)
      deduplicated_data.append(item)
  return deduplicated_data


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
    filtered_papers_metadata = deduplicate_list_of_dicts(filtered_papers_metadata, CONFIG['DATABASE']['OAI_PAPER_TBL_KEY'])
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
    followed_users, followed_tweets = tw.get_user_tweets(top_k=100)
    
    # save user information
    followed_users = deduplicate_list_of_dicts(followed_users, CONFIG['DATABASE']['TW_ACCT_TBL_KEY'])
    df_tw_accts = pd.DataFrame(followed_users)
    df_tw_accts['insert_dt'] = CONFIG['TIME']['CURRENT_DT']
    df_to_sqlite(
        df_tw_accts, 
        table_name = CONFIG['DATABASE']['TW_ACCT_TBL_NM'], 
        db_name = CONFIG['DATABASE']['DB_PATH'] + '/' +  CONFIG['DATABASE']['DB_NAME'],
        if_exists = 'append', 
        id_key = CONFIG['DATABASE']['TW_ACCT_TBL_KEY'])
    
    # save tweets information
    followed_tweets = deduplicate_list_of_dicts(followed_tweets, CONFIG['DATABASE']['TW_TWEET_TBL_KEY'])
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


def get_zotero_items(
        zotero_lib_id: str = CONFIG['API']['ZOTERO_LIB_ID'],
        zotero_api_key:str = CONFIG['API']['ZOTERO_API_KEY'] ):
    """access zotero library to get paper items"""
    try:
        # further 
        from pyzotero import zotero
        zot = zotero.Zotero(library_id=zotero_lib_id, library_type='user', api_key=zotero_api_key) # local=True for read access to local Zotero
        zot_papers = zot.top(limit=20, itemType='book || conferencePaper || journalArticle || preprint')  # itemType refer to zot.item_types()
        return zot_papers
    except Exception as e:
        print(f"Could not access zotero due to {e}")
        return None

async def run_trending_papers(
        model_name: Optional[str] = CONFIG['EMBED']['EMBEDDING_MODEL'],
        keywords:Optional[List[str]]=[],
        zotero_lib_id: Optional[str] = CONFIG['API']['ZOTERO_LIB_ID'],
        zotero_api_key: Optional[str] = CONFIG['API']['ZOTERO_API_KEY']  
    ):
    """calculate semantic similarity between candidate_papers_info (from daily papers) and benchmark_texts (for user defined keywords, or user's existing papers)
    keep only alike papers
    """
    # get zotero papers
    zot_papers = get_zotero_items(zotero_lib_id, zotero_api_key)
    zot_abstracts = [x.get('data', {}).get('abstractNote') for x in zot_papers 
                              if x.get('data', {}).get('abstractNote')]
    
    # from all daily papers
    dly_papers_metadata = await get_dly_papers()
    dly_papers_abstracts = [x.get('abstract', 'NA') for x in dly_papers_metadata]

    # from recommended papers
    recommended_papers_metadata = get_trending_papers()
    rec_papers_abstracts = [x.get('abstract', 'NA') for x in recommended_papers_metadata]
    
    # match daily papers with keywords & zotero papers
    matched_dlypapers_metadata, match_relationships = await filter_by_topics(
        model_name = model_name,
        benchmarks = zot_abstracts + keywords,
        candidates = dly_papers_abstracts + rec_papers_abstracts)
    
    for idx, item in enumerate(match_relationships):
        info = (matched_dlypapers_metadata)[idx]
        # paper = {"title": entry[1].strip(),
        #          "abstract": entry[2].strip(),
        #          "paper_url": entry[3].strip(),
        # }
        print("\n\nSuggested Readings:\n")
        print('```json')
        print(json.dumps(info, ensure_ascii=False, indent=4))
        print('```')
        print("Matched Reasons:\n")
        for x in item.get('matched_info'):
            pos = x.get('candidate_index')
            matched_score = x.get('similarity')
            if pos < len(zot_papers):
                print(f"matched paper '{zot_papers[pos]}', similarity score: {matched_score}")
            else:
                print(f"matched keywords '{keywords[pos]}', similarity score: {matched_score}")

async def main():
    keywords = []  # Example keywords
    await run_trending_papers(keywords=keywords)


if __name__ == "__main__":
    asyncio.run(main())
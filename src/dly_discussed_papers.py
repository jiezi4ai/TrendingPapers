import re
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from json_repair import repair_json  # pip install json-repair https://github.com/mangiucugna/json_repair/

from config import CONFIG
from tools.web_search_tool import WebSearch
from tools.twitter_tool import TwitterKit
from tools.arxiv_tool import ArxivKit


class PapersDiscussed:
    def __init__(
            self,  
            followed_accts: Optional[List[str]] = CONFIG['TWITTER']['FOLLOWED_ACCTS']):
        """Find out papers that discussed in social medium
        """
        self.followed_accts = followed_accts
        self.website = CONFIG['TWITTER']['DETECTED_WEBSITE']
        self.url_pattern = r"(" + "|".join(map(lambda x: x.replace(".", r"\."), self.website)) + ")"

    def get_tweet_urls(self, proxies:Optional[List[str]]=None, max_cnt:Optional[int]=20, past_n_days:Optional[int]=CONFIG['TIME']['TIMELENGTH']):
        """Use google search to get tweet urls for specific twitter account
        Args:
            screen name (str): screen name of twitter account
            max_cnt (int): maximum number of tweet urls
            past_n_days (int): restrict tweet within past n days
        Returns:
            google search result (List of dict), including url, title and descriptoin
        """
        google = WebSearch(proxies=proxies)
        after = (datetime.today() + timedelta(days=-1*past_n_days)).strftime('%Y-%m-%d') 
        search_results = []
        for screen_nm in self.followed_accts:
            query = f"{screen_nm} on x site:x.com after:{after}"
            results = google.google_search_w_retries(query, max_cnt)
            search_results.append(results)
            time.sleep(5)
        return search_results

    def get_all_accts_tweets(self, urls_group, proxies:Optional[List[str]]=None):
        """get followed twitter accounts and top tweets from the accts
        """
        twitter = TwitterKit(proxy_list=proxies)
        followed_users, followed_tweets = [], []
        for idx, urls in enumerate(urls_group):
            screen_nm = self.followed_accts[idx]
            for url in urls:
                # url = rslt.get('url')
                match = match = re.match(r'https://x\.com/([^/]+)/status/(\d+)(?:\?.*)?', url)
                if match:
                    if match.group(1) == screen_nm:
                        tweet_id = match.group(2)
                        print(url, screen_nm, tweet_id)
                        tweet_data, acct_data = twitter.get_tweet_by_id(tweet_id)
                        followed_tweets.append(tweet_data)
                        followed_users.append(acct_data)
        return followed_users, followed_tweets

    def get_arxiv_ids(self, x_accts, x_tweets):
        """get arxiv paper urls and ids from tweet text
        Args:
            tweets: output from get_user_tweets, List of Dict
        """
        tweet_arxiv_info = []

        assert len(x_accts) == len(x_tweets)
        for idx, tweet in enumerate(x_tweets):
            acct_data = x_accts[idx]
            screen_nm = acct_data.get('screen_name')
            tweet_id = tweet.get('id')
            uid = tweet.get('user_id_str')
            full_text = tweet.get('full_text')

            url_info = tweet.get('entities', {}).get('urls', {})
            for item in url_info:
                # identify url with academic website
                if re.search(self.url_pattern, item.get('expanded_url', 'NA')):
                    paper_url = item.get('expanded_url')
                    if 'arxiv.org' in paper_url:
                        arxiv_no = paper_url.split('/')[-1]
                        arxiv_id = re.sub(r'v\d+$', '', arxiv_no)
                        version = re.search(r'v\d+$', arxiv_no)
                        tweet_arxiv_info.append({'x_tweet_id': tweet_id, 
                                                 'arxiv_id': arxiv_id, 
                                                 'x_screen_name': screen_nm,
                                                 'x_uid': uid,
                                                 'x_full_text': full_text})
        return tweet_arxiv_info
    
    
    def retieve_paper_meta(self, tweet_arxiv_info):
        arxiv = ArxivKit()
        arxiv_ids = [x.get('arxiv_id') for x in tweet_arxiv_info]
        papers_metadata = arxiv.retrieve_metadata_by_paper(paper_ids=arxiv_ids)

        papers_info = []
        for idx, meta in enumerate(papers_metadata):
            related_info = tweet_arxiv_info[idx]
            paper_info = {
                    "title": meta.get('title'),
                    "abstract": meta.get('summary'),
                    "paper_url": meta.get('id'),
                    "tweet_url": f"https://x.com/{related_info.get('x_screen_name')}/status/{related_info.get('x_tweet_id')}",
                    "description": related_info.get('x_full_text'),
                    "source": "twitter",
                    "source_url": f"https://x.com/{related_info.get('x_screen_name')}",
                    "extra_info": related_info,
                }
            papers_info.append(paper_info)
        return papers_info

import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from json_repair import repair_json  # pip install json-repair https://github.com/mangiucugna/json_repair/
from fp.fp import FreeProxy  # pip install free-proxy https://github.com/jundymek/free-proxy

from trendingpapers.config import CONFIG
from trendingpapers.tools.twitter_tool import TwitterKit
from trendingpapers.models.default_models import gemini_llm

# proxy
def gen_proxy_list(timeout=5, google_enable=False, anonym=False, filtered=False, https=False):
    return FreeProxy(
        timeout=timeout, 
        google=google_enable, 
        anonym=anonym,
        elite=filtered,
        https=https,
        rand=True).get_proxy_list(repeat=True)

class PapersDiscussed:
    def __init__(
            self, 
            if_proxy: Optional[bool] = False, 
            twitter_accts: Optional[List[str]] = CONFIG['TWITTER']['FOLLOWED_ACCTS']):
        """Find out papers that discussed in social medium
        """
        http_proxies = gen_proxy_list(timeout=5) if if_proxy else None
        self.twitter = TwitterKit(proxy_list=http_proxies)
        self.twitter_accts = twitter_accts
        self.website = CONFIG['TWITTER']['DETECTED_WEBSITE']
        self.url_pattern = r"(" + "|".join(map(lambda x: x.replace(".", r"\."), self.website)) + ")"

    def get_user_tweets(self, top_k=30):
        """get followed twitter accounts and top tweets from the accts
        """
        users_tweets = []
        followed_users, followed_tweets = [], []
        users_ids = []

        for user in self.twitter_accts:
            user_tweet = self.twitter.get_tweets_by_user(user, total=top_k)
            users_tweets.append(user_tweet)

            user_tweets_data = user_tweet.get('data', [])
            for x in user_tweets_data:
                content = x.get('content', {}).get('itemContent', {}).get('tweet_results', {}).get('result', {})
                id = content.get('rest_id')  # tweet_id
                tweet_user_data = content.get('core', {}).get('user_results', {}).get('result', {}).get('legacy', {})  # for user info
                tweet_user_data['user_id_str'] = content.get('core', {}).get('user_results', {}).get('result', {}).get('rest_id')
                tweet_data = content.get('legacy')  # for tweet info
                tweet_data.pop('display_text_range', None)
                tweet_data.pop('extended_entities', None)
                tweet_data['screen_name'] = tweet_user_data.get('screen_name')
                
                followed_tweets.append(tweet_data)
                if tweet_user_data.get('user_id_str') not in users_ids:
                    followed_users.append(tweet_user_data)
                    users_ids.append(tweet_user_data.get('user_id_str'))
        return followed_users, followed_tweets

    def regroup_user_tweets(
            self, 
            tweets: List[Dict], 
            base_dt: str, 
            timelength: int):
        """filter and regroup user tweets
        Args:
            tweets: output from get_user_tweets, List of Dict
        """
        tweet_paper_metadata = []
        other_tweets = []

        for tweet in tweets:
            dt_str = tweet.get('created_at', 'Sat Jan 1 00:00:01 +0000 2000')
            dt_tm = datetime.strptime(dt_str, '%a %b %d %H:%M:%S +0000 %Y')
            base_dt_tm = datetime.strptime(base_dt, '%Y-%m-%d')
            # filter by time
            if dt_tm >= base_dt_tm + timedelta(days=-timelength) and dt_tm <= base_dt_tm + timedelta(days=timelength):
                url_info = tweet.get('entities', {}).get('urls', {})
                flag = 0 
                for item in url_info:
                    # identify url with academic website
                    if re.search(self.url_pattern, item.get('expanded_url', 'NA')):
                        flag = 1
                        paper_url = item.get('expanded_url')
                        break
                if flag == 1:
                    paper_info = {
                        "title": None,
                        "abstract": None,
                        "paper_url": paper_url,
                        "tweet_url": f"https://x.com/{tweet.get('screen_name')}/status/{tweet.get('id_str')}",
                        "description": tweet.get('full_text'),
                        "source": "twitter",
                        "source_url": f"https://x.com/{tweet.get('screen_name')}",
                        "extra_info": tweet,
                    }
                    tweet_paper_metadata.append(paper_info)
                else:
                    other_tweets.append(tweet)
        return tweet_paper_metadata, other_tweets
    
    def llm_regroup_tweets(self, tweets,):
        """use LLM to identify if tweets is paper related"""
        llm_tweet_info = []
        for item in tweets:
            llm_tweet_info.append({'id': item.get('id_str'),
                            'user': item.get('screen_name'),
                            'text': item.get('full_text')})
        llm_tweet_data = json.dumps(llm_tweet_info, ensure_ascii=False, indent=2)

        def llm_identify_tweets(tweets, api_key=CONFIG['LLM']['GEMINI_API_KEY'], model_name=CONFIG['LLM']['GEMINI_MDL_NM']):
            sys_prompt = """You are a proficient academic researcher. 
            So far you have extracted tweets from Twitter, now your task is to identify if the tweets relate to '{domain}' research or papers and output them in json format.

            The input format is a list of dictionaries, each containing the tweet ID, the user who posted the tweet, and the tweet text, as follows:
            {"id": "1234567890123456789", "user": "username", "text": "Tweet text."}

            You are suppose to categorize each tweet into one of the three groups:
            - "paper_related": tweets that closely related to academic paper
            - "non_related": tweets that not related to academic paper
            - "TBD": not yet clear based on given tweet

            Output format as follows:
            {"paper_related":["related tweet id", "related tweet id", ...],
            "non_related":["related tweet id", "related tweet id", ...],
            "TBD":["related tweet id", "related tweet id", ...],
            }
            """

            qa_prompt = """Now, please process the following list of dictionaries and generate the corresponding output.
            ```json
            {tweets}
            ```
            """
            response = gemini_llm(    
                api_key, 
                model_name,  
                qa_prompt = qa_prompt.format(tweets=tweets), 
                sys_prompt=sys_prompt, 
                temperature=0.1)
            return response
        
        response = llm_identify_tweets(llm_tweet_data)
        paper_regroup = (json.loads(repair_json(response)))
        return paper_regroup
    
        
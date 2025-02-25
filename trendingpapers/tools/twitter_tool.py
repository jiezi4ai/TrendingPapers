# twitter_tool.py
# TO-DO: 
# 1. save intermediate results
# 2. improve async_get_tweets_by_id
# 3. add async functions
# 4. extract user, tweet objects

import time
import random
import requests
import pandas as pd
from typing import Dict, List

from tweeterpy import TweeterPy  # pip install tweeterpy https://github.com/iSarabjitDhiman/TweeterPy

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MAX_RETRIES = 5
BACKOFF_FACTOR = 0.5
X_ALTER_URL = "https://xapi.betaco.tech/x-thread-api?url="

_useragent_list = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.62',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0'
]

class TwitterKit:
    def __init__(
            self, 
            proxy_list, 
            user_agents=None, 
            timeout=10, 
            max_retries=MAX_RETRIES, 
            ssl_verify=False
        ):
        # for general settings
        if user_agents is None:
            self.user_agents = _useragent_list
        else:
            self.user_agents = user_agents
        self.proxies = proxy_list
        self.timeout = timeout
        self.max_retries = max_retries
        self.ssl_verify = ssl_verify
        self.sessions = {}  # Dictionary to store requests.Session objects per proxy
        self.tw_clients = {}  # Dictionary to store TweeterPy clients per proxy
        
    def _get_session(self, proxy=None):
        """Gets or creates a requests.Session object, optionally with proxy settings."""
        if proxy:
            if proxy not in self.sessions:
                self.sessions[proxy] = requests.Session()
                self.sessions[proxy].proxies = {'http': proxy}
            return self.sessions[proxy]
        else:
            if None not in self.sessions:
                self.sessions[None] = requests.Session()
            return self.sessions[None]

    def _get_tw_client(self, proxy=None):
        """Gets or creates a TweeterPy client, optionally with proxy settings."""
        if proxy not in self.tw_clients or self.tw_clients[proxy] is None:
            session = self._get_session(proxy)
            try:
                self.tw_clients[proxy] = TweeterPy(
                    proxies=session.proxies if session.proxies else None, log_level="INFO"
                )
            except Exception as e:
                logging.error(f"Failed to create TweeterPy client with proxy {proxy}: {e}")
                self.tw_clients[proxy] = None
        return self.tw_clients[proxy]

    def _invalidate_tw_client(self, proxy):
        """Invalidates the TweeterPy client for a given proxy."""
        if proxy in self.tw_clients:
            self.tw_clients[proxy] = None

    def _make_request(self, func, *args, **kwargs):
        """Helper function to handle retries and common error handling."""
        retries = 0
        proxy = None
        while retries <= self.max_retries:
            if self.proxies:
                proxy = random.choice(self.proxies)  # Rotate proxy randomly
            try:
                result = func(proxy, *args, **kwargs)
                if result is not None:
                    return result
            except requests.exceptions.RequestException as e:
                logging.warning(
                    f"Request failed (attempt {retries + 1}/{self.max_retries + 1}) with proxy {proxy}: {e}"
                )
                self._invalidate_tw_client(proxy)  # Invalidate on request failure
                retries += 1
                time.sleep(BACKOFF_FACTOR * (2 ** retries))  # Exponential backoff
            except Exception as e:
                logging.error(f"An unexpected error occurred with proxy {proxy}: {e}")
                self._invalidate_tw_client(proxy)  # Also invalidate on unexpected errors
                return None

        logging.error(f"Max retries exceeded ({self.max_retries}).")
        return None

    def get_userid(self, username):
        """Get user ID based on user name (screen name like 'elonmusk')."""
        def _get_userid_inner(proxy, username):
            tw_client = self._get_tw_client(proxy)
            if tw_client is None:
                return None
            try:
                uid = tw_client.get_user_id(username)
                return uid
            except Exception as e:
                logging.error(f"Error with TweeterPy().get_user_id('{username}') using proxy {proxy}: {e}")
                self._invalidate_tw_client(proxy)
                raise  # Re-raise to trigger retry

        return self._make_request(_get_userid_inner, username)

    def get_userdata(self, username):
        """get user profile based on user name (screen name like 'elonmusk')
        Args:
            username (str): user name (screen name like 'elonmusk')
        """
        def _get_userdata_inner(proxy, username):
            tw_client = self._get_tw_client(proxy)
            if tw_client is None:
                return None
            try:
                user_profile = tw_client.get_user_data(username)
                return user_profile
            except Exception as e:
                logging.error(f"Error with TweeterPy().get_user_data('{username}') using proxy {proxy}: {e}")
                self._invalidate_tw_client(proxy)
                raise

        return self._make_request(_get_userdata_inner, username)

    def get_tweets_by_user(self, username, total=20):
        """get user tweets based on user name (screen name like 'elonmusk')
        Args:
            username (str): user name (screen name like 'elonmusk')
        """
        def _get_usertweets_inner(proxy, username, total):
            tw_client = self._get_tw_client(proxy)
            if tw_client is None:
                return None
            try:
                user_tweets = tw_client.get_user_tweets(
                    username, with_replies=False, end_cursor=None, total=total, pagination=True
                )
                return user_tweets
            except Exception as e:
                logging.error(f"Error with TweeterPy().get_user_tweets('{username}') using proxy {proxy}: {e}")
                self._invalidate_tw_client(proxy)
                raise

        return self._make_request(_get_usertweets_inner, username, total)

    def get_tweet_by_id(self, tweet_id):
        """Retrieves a tweet, first trying TweeterPy and then falling back to a direct API request.
        Args:
            username (str): user name (screen name like 'elonmusk')
            tweet_id (str): status id of tweet url
        Returns:
            tweet_dct (dict): information including tweet, user, and api usage
        Usage:
            id = tweet_dct.get('rest_id')  # tweet_id
            usage_data = tweet_dct.get('api_rate_limit')  # for api rate limit information
            tweet_info= tweet_dct.get('data', {}).get('tweetResult', {}).get('result', {})
            tweet_user_data = tweet_info.get('core', {}).get('user_results', {}).get('result', {})  # for user info
            tweet_data = tweet_info.get('legacy')  # for tweet info
        """
        def _get_tweet_by_id_inner(proxy, tweet_id):
            tw_client = self._get_tw_client(proxy)
            if tw_client is not None:
                try:
                    tweet = tw_client.get_tweet(
                        tweet_id=tweet_id,
                        with_tweet_replies=False,
                        end_cursor=None,
                        total=None,
                        pagination=True
                    )
                    return tweet
                except Exception as e:
                    logging.warning(f"TweeterPy failed to get tweet using proxy {proxy}: {e}. Trying direct API request...")
                    self._invalidate_tw_client(proxy)
        
        return self._make_request(_get_tweet_by_id_inner, tweet_id)

    def scrape_tweet_by_id(self, username, tweet_id):
        """scrape tweet using alternative urls
        Args:
            username (str): user name (screen name like 'elonmusk')
            tweet_id (str): status id of tweet url
        Returns:
            tweet_dcts (list of dict): 
                  a simplified version of tweet dicts, including only author, text, tweet_id, timestamp, media, links.
                  include multiple tweet under same user.
        """
        def _scrape_tweet_by_id_inner(proxy, username, tweet_id):
           try:
                session = self._get_session(proxy)
                link = f"{X_ALTER_URL}https://x.com/{username}/status/{tweet_id}"
                custom_headers = {"User-Agent": random.choice(self.user_agents)}
                response = session.get(
                    url=link,
                    headers=custom_headers,
                    timeout=self.timeout,
                    verify=self.ssl_verify
                )
                response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
                return response.json()
           except requests.exceptions.RequestException as e:
                logging.error(f"Direct API request failed using proxy {proxy}: {e}")
                raise  # Re-raise to trigger retry in _make_request   
        return self._make_request(_scrape_tweet_by_id_inner, username, tweet_id) 
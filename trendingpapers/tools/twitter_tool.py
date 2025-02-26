# twitter_tool.py
# TO-DO: 
# 1. save intermediate results
# 2. add async functions
# 3. extract user, tweet objects

import copy
import time
import datetime
import random
import requests
from typing import Dict, List, Optional, Set, Literal

from tweeterpy import TweeterPy  #   pip install tweeterpy https://github.com/iSarabjitDhiman/TweeterPy

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MAX_RETRIES = 5
BACKOFF_FACTOR = 0.5
RESET_TIME_INTERVAL = 900  # rate limit reset time interval in seconds
RATE_LIMIT = 50  # number of rate limit (# of calls)
OVERALL_RATE_LIMIT = 600  # overall rate limit of a day


def rename_key_in_dict(input_dict, key_mapping):
    """rename keys in dict
    Args:
        key_mapping: Mapping of old keys to new keys, in format like: {"old_name_1": "new_name_1", "old_name_2": "new_name_2", ...}  
    """
    return {key_mapping.get(k, k): v for k, v in input_dict.items()}

def remove_key_values(input_dict, keys_to_delete):
    """delete key-value in dict"""
    opt_dct = copy.deepcopy(input_dict)
    for key in keys_to_delete:
        if key in opt_dct:  # 检查键是否存在，避免 KeyError
            del opt_dct[key]
    return opt_dct # 为了方便链式调用，返回修改后的字典


# for data alignment purpose
def align_acct_data(tweeterpy_acct_data):
    """process acct information from TweeterPy"""
    acct_info = tweeterpy_acct_data.get('legacy')
    
    # generate new keys
    acct_info['_client'] = 'tweeterpy_client'
    acct_info['id'] = tweeterpy_acct_data.get('rest_id')
    acct_info['is_blue_verified'] = tweeterpy_acct_data.get('is_blue_verified')
    acct_info['urls'] = tweeterpy_acct_data.get('legacy', {}).get('entities', {}).get('url', {}).get('urls')
    acct_info['description_urls'] = tweeterpy_acct_data.get('legacy', {}).get('entities', {}).get('description', {}).get('urls')
    
    # rename keys
    keys_mapping = {'profile_image_url_https': 'profile_image_url', 
                    'pinned_tweet_ids_str': 'pinned_tweet_ids',
                    'friends_count': 'following_count'}
    acct_info = rename_key_in_dict(acct_info, keys_mapping)

    # drop keys
    delete_keys = ['entities', 'profile_interstitial_type']
    acct_info = remove_key_values(acct_info, delete_keys)

    return acct_info

def align_tweet_data(tweeterpy_tweet_data):
    # tweeterpy_tweet_data = result.get('data', {}).get('tweetResult', {}) or result.get('data', {}).get('tweetResults', {})
    info = tweeterpy_tweet_data.get('result', {})

    # for acct info
    acct_data = info.get('core', {}).get('user_results', {}).get('result', {})
    acct_data = align_acct_data(acct_data)

    # for tweet info
    tweet_data = info.get('legacy')
    tweet_data['id'] = info.get('rest_id')

    return tweet_data, acct_data


class TwitterKit:
    def __init__(
            self, 
            proxy_list, 
            max_retires: Optional[int] = MAX_RETRIES
        ):
        """initiate twitter tools and set up parameters
        Args:
            proxy_lst: list of proxies in format like 'ip_addr:port'. support http proxies for now.
            x_login_name, x_password, x_login_email: X related login information. 
        Note:
            1. tweeterpy_client (based on tweeterpy package) is set up to get user id, user data and tweet given specific id.
            3. tweeterpy_client does not require login credentials, while twikit_client requires X related login information.
            4. tweeterpy_client is bound to rate limits constraint. It may resort to proxy to get over it.
            6. tweeterpy_clients_usage records client / proxy usage information for tweeterpy_client. It includes:
                - proxy: proxy used
                - initiate_tm: client first initiated
                - last_call_tm: client last called with API usage
                - remaining_requests: remaining usage cnt
                - next_reset_tm: rate limit next reset time
        """
        self.max_retires = max_retires

        self.tweeterpy_clients_usage = [{'proxy': proxy} for proxy in proxy_list]  # save client / proxy usage information
        self.twikit_client_usage = {}
        self.current_proxy = None

    def _load_tweeterpy_client(self, excluded_proxies: Optional[Set]=set()):
        """"load tweeterpy client
        Args:
            excluded_proxies: a set object with excluded proxies. (proxies connetable but may not work for specific function)
        """
        flag = 0

        # iterate all clients for usable one (both with connectable proxy and usage within rate limits)
        for idx, client_uage in enumerate(self.tweeterpy_clients_usage):
            if (client_uage.get('proxy') in excluded_proxies
                or client_uage.get('is_bad_proxy', False) == True   # client with bad proxy
                or (client_uage.get('remaining_requests', 20) <= 0 and client_uage.get('next_reset_tm') > int(time.time()))  # client restricted by rate limit
                ):
                continue
            else:
                try:
                    self.tweeterpy_client= TweeterPy(
                        proxies={'http': client_uage.get('proxy')}, 
                        log_level="INFO"
                    )
                    test_uid = self.tweeterpy_client.get_user_id('elonmask')  # test if client works
                    client_uage['initiate_tm'] = int(time.time())
                    self.current_proxy = client_uage['proxy']
                    flag = 1
                    break
                except Exception as e:
                    logging.warning(f"Failed to create TweeterPy client with proxy {client_uage['proxy']}: {e}")
                    client_uage['is_bad_proxy'] = True

        # no usable client
        if flag == 0:  
            logging.error(f"Exhausted all proxies and still could not establish TweeterPy client.")
            self.tweeterpy_client = None
            self.current_proxy = None


    def get_user_id(self, username) -> str:
        """Get user ID based on user name (screen name like 'elonmusk')."""
        attempt = 0
        excluded_proxies = set()
        while attempt < self.max_retires:
            try:
                uid = self.tweeterpy_client.get_user_id(username)
                return uid
            except Exception as e:
                excluded_proxies.add(self.current_proxy)
                self._load_tweeterpy_client(excluded_proxies)
                attempt += 1
        return None


    def get_user_info(self, username):
        """get user profile based on user name (screen name like 'elonmusk')
        Args:
            username (str): user name (screen name like 'elonmusk')
        Usage:
            uid = user_data.get('rest_id')
            tweet_acct_info = user_data.get('legacy')
        """
        attempt = 0
        excluded_proxies = set()
        while attempt < self.max_retires:
            try:
                user_info = self.tweeterpy_client.get_user_data(username)
                break
            except Exception as e:
                excluded_proxies.add(self.current_proxy)
                self._load_tweeterpy_client(excluded_proxies)
                attempt += 1
        
        # decode user info
        if user_info:
            try:
                return align_acct_data(user_info)
            except Exception as e:
                print(f"TweeterPy decode error: {e}")
        return None


    def get_tweet_by_id(self, tweet_id):
        """Retrieves a tweet given specific tweet id.
        Args:
            username (str): user name (screen name like 'elonmusk')
            tweet_id (str): status id of tweet url
        Returns:
            tweet_dct (dict): information including tweet, user, and api usage
        Usage:
            tweet_id = tweet_dct.get('rest_id')  # tweet_id
            usage_data = tweet_dct.get('api_rate_limit')  # for api rate limit information
            tweet_info= tweet_dct.get('data', {}).get('tweetResult', {}).get('result', {})
            tweet_user_data = tweet_info.get('core', {}).get('user_results', {}).get('result', {})  # for user info
            tweet_data = tweet_info.get('legacy')  # for tweet info
        """
        attempt = 0
        excluded_proxies = set()
        while attempt < self.max_retires:
            try:
                tweet_info = self.tweeterpy_client.get_tweet(tweet_id)
                api_limit = tweet_info.get('api_rate_limit', {})
                # update client usage info
                idx = [x['proxy'] for x in self.tweeterpy_clients_usage].index(self.current_proxy)
                self.tweeterpy_clients_usage[idx]['last_call_tm'] = int(time.time())
                self.tweeterpy_clients_usage[idx]['remaining_requests'] = api_limit.get('remaining_requests_count')
                self.tweeterpy_clients_usage[idx]['next_reset_tm'] = int((datetime.datetime.now() + api_limit.get('reset_after_datetime_object')).timestamp())
                break
            
            except Exception as e:
                excluded_proxies.add(self.current_proxy)
                self._load_tweeterpy_client(excluded_proxies)
                attempt += 1
        
        # decode tweet info
        if tweet_info:
            try:
                tweet_data, acct_data = align_tweet_data(tweet_info.get('data', {}).get('tweetResult', {}))
                return tweet_data, acct_data
            except Exception as e:
                print(f"TweeterPy decode error: {e}")
        return None, None


    def get_tweets_by_user(self, username, total=20):
        """get user tweets based on user name (screen name like 'elonmusk').
           Not recommended since the tweets retrived are not arranged in time sequence.
        Args:
            username (str): user name (screen name like 'elonmusk')
        """
        attempt = 0
        excluded_proxies = set()
        while attempt < self.max_retires:
            try:
                user_tweets_info = self.tweeterpy_client.get_user_tweets(username, total=total)
                api_limit = user_tweets_info.get('api_rate_limit', {})
                # update client usage info
                idx = [x['proxy'] for x in self.tweeterpy_clients_usage].index(self.current_proxy)
                self.tweeterpy_clients_usage[idx]['last_call_tm'] = int(time.time())
                self.tweeterpy_clients_usage[idx]['remaining_requests'] = api_limit.get('remaining_requests_count')
                self.tweeterpy_clients_usage[idx]['next_reset_tm'] = int((datetime.datetime.now() + api_limit.get('reset_after_datetime_object')).timestamp())
                break
            
            except Exception as e:
                excluded_proxies.add(self.current_proxy)
                self._load_tweeterpy_client()
                attempt += 1

        # decode tweet info
        if user_tweets_info and len(user_tweets_info) > 0:
            try:
                accts_data, tweets_data = [], []
                for item in user_tweets_info.get('data', []):
                    item_info = item.get('content', {}).get('itemContent')
                    tweet_data, acct_data = align_tweet_data(item_info.get('tweet_results', {})) 
                    accts_data.append(acct_data)
                    tweets_data.append(tweet_data)
                return tweets_data, accts_data
            except Exception as e:
                print(f"TweeterPy decode error: {e}")
        return None, None
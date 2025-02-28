import copy
import time
import datetime
import requests
from typing import Dict, List, Optional, Set, Tuple

from tweeterpy import TweeterPy  #   pip install tweeterpy https://github.com/iSarabjitDhiman/TweeterPy
from tweeterpy.util import RateLimitError

# Configure logging
import logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

MAX_RETRIES = 5
BACKOFF_FACTOR = 0.5
DEFAULT_REMAINING_REQUESTS_THRESHOLD = 20 # Define constant for magic number

ACCOUNT_KEY_MAPPING = {
    'profile_image_url_https': 'profile_image_url',
    'pinned_tweet_ids_str': 'pinned_tweet_ids',
    'friends_count': 'following_count'
}

ACCOUNT_DELETE_KEYS = ['entities', 'profile_interstitial_type']

def rename_key_in_dict(input_dict, key_mapping):
    """Renames keys in a dictionary.
    Args:
        key_mapping: Mapping of old keys to new keys, 
                     e.g., {"old_name_1": "new_name_1", "old_name_2": "new_name_2", ...}
    Returns:
        A new dictionary with renamed keys.
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
    """Processes account information from TweeterPy to align data format.
    Args:
        tweeterpy_acct_data (dict): Account data from TweeterPy.

    Returns:
        dict: Aligned account information.
    """
    acct_info = tweeterpy_acct_data.get('legacy', {}) # Default to empty dict to avoid errors

    # Generate new keys - use .get() with defaults for robustness
    acct_info['_client'] = 'tweeterpy_client'
    acct_info['id'] = tweeterpy_acct_data.get('rest_id')
    acct_info['is_blue_verified'] = tweeterpy_acct_data.get('is_blue_verified')
    acct_info['urls'] = tweeterpy_acct_data.get('legacy', {}).get('entities', {}).get('url', {}).get('urls')
    acct_info['description_urls'] = tweeterpy_acct_data.get('legacy', {}).get('entities', {}).get('description', {}).get('urls')

    # Rename keys using constant mapping
    acct_info = rename_key_in_dict(acct_info, ACCOUNT_KEY_MAPPING)

    # Drop keys using constant list
    acct_info = remove_key_values(acct_info, ACCOUNT_DELETE_KEYS)

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
        self._load_tweeterpy_client()


    def _load_tweeterpy_client(self, excluded_proxies: Optional[Set]=set()):
        """Loads a usable TweeterPy client.
        Iterates through available proxies to find one that is connectable, 
        not marked as bad, and not rate-limited.
        Args:
            excluded_proxies (Optional[Set], optional): A set of proxies to exclude. 
                                                        Defaults to an empty set.
        """
        flag = 0

        # Iterate all clients for usable one (connectable proxy and within rate limits)
        for idx, client_usage in enumerate(self.tweeterpy_clients_usage):
            proxy_status = client_usage.get('proxy') in excluded_proxies or \
                           client_usage.get('is_bad_proxy', False) or \
                           (client_usage.get('remaining_requests', DEFAULT_REMAINING_REQUESTS_THRESHOLD) <= 0 and \
                            client_usage.get('next_reset_tm', 0) > int(time.time()))

            if proxy_status:
                continue # Skip to next proxy if current proxy is excluded, bad, or rate-limited
            else:
                try:
                    self.tweeterpy_client = TweeterPy(
                        proxies={'http': client_usage.get('proxy')},
                        log_level="WARNING"
                    )
                    test_uid = self.tweeterpy_client.get_user_id('elonmask')  # Test if client works
                    client_usage['initiate_tm'] = int(time.time())
                    self.current_proxy = client_usage['proxy']
                    flag = 1
                    break # Exit loop once a usable client is found

                except requests.exceptions.ConnectionError as e: # Be specific with exception type
                    logging.warning(f"Connection error with proxy {client_usage['proxy']}: {e}")
                    client_usage['is_bad_proxy'] = True
                    continue # Try next proxy

                except Exception as e: # Catch other potential exceptions during client loading
                    logging.warning(f"Error loading client with proxy {client_usage['proxy']}: {e}")
                    client_usage['is_bad_proxy'] = True
                    continue # Stop trying proxies if a non-connection related error occurs

        if flag == 0: # No usable client found
            logging.error("Exhausted all proxies, could not establish TweeterPy client.")
            self.tweeterpy_client = None
            self.current_proxy = None


    def get_user_id(self, username) -> Optional[str]: # More specific return type hint
        """Gets user ID based on username (screen name like 'elonmusk').
        Args:
            username (str): Twitter screen name (e.g., 'elonmusk').
        Returns:
            Optional[str]: User ID as a string, or None if retrieval fails after retries.
        """
        attempt = 0
        excluded_proxies = set()
        while attempt < self.max_retires:
            try:
                uid = self.tweeterpy_client.get_user_id(username)
                return uid # Return user ID immediately on success

            except requests.exceptions.ConnectionError as e: # Specific ConnectionError
                logging.warning(f"Connection error for user ID lookup of '{username}' using proxy {self.current_proxy}, retrying... (Attempt {attempt + 1}/{self.max_retires})")
                excluded_proxies.add(self.current_proxy)
                self._load_tweeterpy_client(excluded_proxies) # Load new client with proxy rotation
                attempt += 1
                continue # Retry with new client/proxy

            except Exception as e: # Catch other exceptions
                logging.error(f"Error getting user ID for '{username}' after {attempt + 1} attempts. Error: {e}")
                return None # Return None on general error after retries

        logging.error(f"Failed to get user ID for '{username}' after {self.max_retires} retries.") # Log if max retries reached
        return None # Return None if max retries exceeded


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
            except ConnectionError as e:
                excluded_proxies.add(self.current_proxy)
                self._load_tweeterpy_client(excluded_proxies)
                attempt += 1
                continue
            except Exception as e:
                logging.error(f"Unable to get user data for {username}. Error code: {e}")
                return None
        
        # decode user info
        if user_info:
            try:
                return align_acct_data(user_info)
            except Exception as e:
                logging.error(f"TweeterPy decode error: {e}")
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
                break # Success! Exit retry loop

            except requests.exceptions.ConnectionError as e:
                logging.warning(f"Connection error for tweet ID '{tweet_id}' using proxy {self.current_proxy}, retrying... (Attempt {attempt + 1}/{self.max_retires})")
                excluded_proxies.add(self.current_proxy)
                self._load_tweeterpy_client(excluded_proxies)
                attempt += 1
                continue # Retry with proxy rotation

            except RateLimitError as e:
                logging.warning(f"Rate limit hit for tweet ID '{tweet_id}' using proxy {self.current_proxy}, retrying with proxy rotation... (Attempt {attempt + 1}/{self.max_retires})")
                # Consider adding time.sleep(some_backoff_duration) here
                self._load_tweeterpy_client(excluded_proxies)
                attempt += 1
                continue # Retry with proxy rotation

            except Exception as e:
                logging.error(f"Error getting tweet data for tweet ID '{tweet_id}' after {attempt + 1} attempts. Error: {e}")
                return None, None # Return None, None on general error after retries

        # decode tweet info
        if tweet_info:
            try:
                tweet_result = tweet_info.get('data', {}).get('tweetResult', {}) or {} # Default to empty dict
                tweet_data, acct_data = align_tweet_data(tweet_result)
                return tweet_data, acct_data
            except Exception as e:
                logging.error(f"TweeterPy decode error for tweet ID '{tweet_id}': {e}") # Include tweet_id in decode error log
        return None, None # Return None, None if tweet_info is empty or decoding fails


    def get_tweets_by_user(self, username, total=20) -> Tuple[Optional[List[Dict]], Optional[List[Dict]]]:
        """Gets user tweets based on username (screen name like 'elonmusk').
            Not recommended for timeline retrieval as tweets might not be in time sequence 
            and the total number of tweets retrievable might be limited. 
            Consider using a more robust timeline API if chronological order and completeness are critical.

        Args:
            username (str): Twitter screen name (e.g., 'elonmusk').
            total (int, optional): Number of tweets to attempt to retrieve. Defaults to 20.

        Returns:
            Tuple[Optional[List[Dict]], Optional[List[Dict]]]: 
            A tuple containing two lists: 
                - List of tweet data dictionaries, or None if retrieval fails.
                - List of user account data dictionaries corresponding to the tweets, or None if retrieval fails.
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
                break # Success! Exit retry loop

            except requests.exceptions.ConnectionError as e:
                logging.warning(f"Connection error for user tweets of '{username}' using proxy {self.current_proxy}, retrying... (Attempt {attempt + 1}/{self.max_retires})")
                excluded_proxies.add(self.current_proxy)
                self._load_tweeterpy_client(excluded_proxies)
                attempt += 1
                continue # Retry with proxy rotation

            except RateLimitError as e:
                logging.warning(f"Rate limit hit for user tweets of '{username}' using proxy {self.current_proxy}, retrying with proxy rotation... (Attempt {attempt + 1}/{self.max_retires})")
                # Consider adding time.sleep(some_backoff_duration) here
                self._load_tweeterpy_client(excluded_proxies)
                attempt += 1
                continue # Retry with proxy rotation

            except Exception as e:
                logging.error(f"Error getting tweet data for user '{username}' after {attempt + 1} attempts. Error: {e}")
                return None, None # Return None, None on general error after retries

        # decode tweet info
        if user_tweets_info and user_tweets_info.get('data'): # More explicit check for data
            try:
                accts_data, tweets_data = [], []
                for item in user_tweets_info.get('data', []): # Iterate through data list
                    item_info = item.get('content', {}).get('itemContent', {}) # Deeper .get() with defaults
                    tweet_results = item_info.get('tweet_results', {}) # Deeper .get() with defaults
                    tweet_data, acct_data = align_tweet_data(tweet_results) # Align data for each tweet
                    if tweet_data and acct_data: # Only append if data is successfully aligned
                        accts_data.append(acct_data)
                        tweets_data.append(tweet_data)
                return tweets_data, accts_data
            except Exception as e:
                logging.error(f"TweeterPy decode error for user '{username}': {e}") # Include username in decode error log
        return None, None # Return None, None if no user_tweets_info or data is empty or decoding fails
import time
import requests
from typing import Dict, List, Optional

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from trendingpapers.tools.google_search import SearchClient

MAX_RESULTS = 100
MAX_RETRIES = 5
RETRY_DELAY_SECONDS = 60  # Define retry delay as a constant
RETRY_DELAY_SECONDS_AFTER429 = 30  # Define retry delay as a constant

class WebSearch:
    """
    A class for performing web searches, primarily using Google, with proxy support and retry mechanisms.
    """
    def __init__(
            self,
            proxies: Optional[List[str]] = None,
            max_results: int = MAX_RESULTS,
            max_retries: int = MAX_RETRIES):
        """
        Initializes the WebSearch class.

        Args:
            proxies (Optional[List[str]]): A list of proxy servers to use (e.g., ['http://proxy1:port', 'http://proxy2:port']). Defaults to None (no proxies).
            max_results (int): Maximum number of search results to retrieve per query. Defaults to MAX_RESULTS.
            max_retries (int): Maximum number of retries for proxy connections. Defaults to MAX_RETRIES.
        """
        self.proxies = proxies if proxies else [] # Ensure proxies is always a list
        self.max_results = max_results
        self.max_retries = max_retries
        
    def yagooglesearch(self, query:str, proxy:Optional[str]=None, max_results:Optional[int]=None, with_detail:Optional[bool]=False):
        """call SearchClient to conduct search"""
        max_results = self.max_results if max_results is None else max_results
        client = SearchClient(
                query,
                lang_html_ui= "en",
                lang_result = "lang_en",
                start = 0,
                num = min(100, max_results),
                max_search_result_urls_to_return = min(100, max_results),
                minimum_delay_between_paged_results_in_seconds = 30,
                proxy=proxy,
                # user_agent = None,
                # verify_ssl = False,
                verbosity = 0,
                yagooglesearch_manages_http_429s = False,  # Disable automatic 429 handling for custom logic
                verbose_output = with_detail,
                )
        client.assign_random_user_agent()
        search_results = client.search()
        return search_results
        
    def google_search_w_retries(self, query: str, max_results: Optional[int] = None, with_detail:Optional[bool]=False):
        """Search google with retries.
        Args:
            query (str): Search query.
            max_results (Optional[int]): Maximum number of search results to retrieve. Defaults to class's max_results.
        Returns:
            List[Dict[str, str]]: Query results in list of dict format.
            Each dict contains: {"rank": str, "title": str, "description": str, "url": str}
            Returns an empty list if no results are found or all retries fail.
        """
        error_count = 0
        
        results = [] # Initialize results as empty list
        if self.proxies and error_count < self.max_retries: 
            for proxy in self.proxies:
                try:
                    search_results = self.yagooglesearch(query, proxy, max_results, with_detail)

                    # Robust HTTP 429 detection (if yagooglesearch exposes status codes, use that)
                    if search_results and "HTTP_429_DETECTED" in search_results: 
                        error_count += 1
                        logging.warning(f"Proxy {proxy} returned 429. Retrying with a different proxy.")
                        self.proxies.remove(proxy) # Consider removing proxy on 429, or implement health check
                        time.sleep(RETRY_DELAY_SECONDS_AFTER429)
                        continue # Try next proxy

                    elif search_results:
                        logging.info(f"Search successful using proxy: {proxy}")
                        return search_results # Return results on success

                except requests.exceptions.RequestException as e: # Catch specific request exceptions
                    error_count += 1
                    self.proxies.remove(proxy)
                    logging.info(f"Request error with proxy {proxy}: {e}. Retrying with a different proxy.")
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue # Try next proxy
                
                except Exception as e: # Catch other potential exceptions from yagooglesearch
                    error_count += 1
                    logging.error(f"Unexpected error during search with proxy {proxy}: {e}")
                    break

            if not results and self.proxies: # Log if proxies are exhausted
                logging.warning("All proxies failed or exhausted. Falling back to search without proxy if possible.")

        logging.info("Searching without proxy.") # Log when searching without proxy
        try:
            results = self.yagooglesearch(query, None, max_results, with_detail) # Try search without proxy
            return results
        except Exception as e:
            logging.error(f"Search without proxy failed: {e}")
            return [] # Return empty list if even proxy-less search fails
        

import pandas as pd
from datetime import datetime
from typing import Dict, List
import yagooglesearch  # https://github.com/opsdisk/yagooglesearch

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MAX_RESULTS = 100
MAX_RETRIES = 5

class GoogleSearchKit:
    def __init__(
            self, 
            proxies=None, 
            max_results=MAX_RESULTS, 
            max_retries=MAX_RETRIES):
        self.max_results = max_results
        self.proxies = proxies
        self.max_retries = max_retries

    def google_search_w_proxies(self, query, max_results=None):
        """Search google with proxies
        Args:
            :param str query: search query
        Returns:
            :returns: query results in list of dict format.
            {"rank": int, "title": str, "description": str, "url": str}
        """
        error_count = 0
        client = yagooglesearch.SearchClient(
            query,
            tbs="li:1",
            max_search_result_urls_to_return=max_results if max_results else self.max_results,
            http_429_cool_off_time_in_minutes=45,
            http_429_cool_off_factor=1.5,
            verbosity=5,
            verbose_output=True,  # False (only URLs) or True (rank, title, description, and URL)
        )
        if self.proxies is not None:
            for proxy in self.proxies:
                if error_count < self.max_retries:
                    try:
                        client.proxy = f"http://{proxy}"
                        client.assign_random_user_agent()
                        results = client.search()
                        return results
                    except Exception as e:
                        logging.error(f"Error occurred in search: {e}")
                        error_count += 1
                else:
                    break
        else:
            logging.warning("Proxies unavailable. Search without proxy.")
            client.assign_random_user_agent()
            results = client.search()
            return results
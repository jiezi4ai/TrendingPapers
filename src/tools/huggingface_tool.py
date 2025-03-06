import json
import random
import requests
from requests.adapters import Retry, HTTPAdapter
from datetime import datetime
import logging

from json_repair import repair_json  # https://github.com/mangiucugna/json_repair/
from firecrawl import FirecrawlApp  # pip install firecrawl-py https://github.com/mendableai/firecrawl

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

_useragent_list = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.62',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0'
]

class HuggingFaceKit:
    def __init__(self, max_retries_cnt=3, firecrawl_api_key=None):
        self.base_url = "https://huggingface.co/api/daily_papers"
        self.headers = {
            "User-Agent": random.choice(_useragent_list)
        }
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries_cnt,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        if firecrawl_api_key is not None:
            self.firecrawl = FirecrawlApp(api_key=firecrawl_api_key)


    def fetch_daily_papers(self, date_str=None, max_cnt=None):
        logger.info(f"Retrieve HuggingFace Daily Paper.")
        
        # 构建API URL
        if date_str is not None and max_cnt is not None:
            url = f"{self.base_url}?date={date_str}&limit={max_cnt}"
        elif date_str is not None:
            url = f"{self.base_url}?date={date_str}"
        elif max_cnt is not None:
            url = f"{self.base_url}?limit={max_cnt}"
        else:
            url = self.base_url 

        try:
            response = self.session.get(url, headers=self.headers, timeout=10) # 添加 timeout
            response.raise_for_status()
            data = response.json()

            if not data:
                print("No data received from API.")

            # Debug: Print keys of the first paper
            if data: 
                hf_paper_dicts = [item.get('paper') for item in data]
                return hf_paper_dicts
            else:
                return []

        except requests.exceptions.RequestException as e: # 捕获更具体的 requests 异常
            print(f"Error fetching papers through API: {e}\nSwitch to FireCrawl:\n")
            if self.firecrawl is not None:
                try:
                    response = self.firecrawl.scrape_url(url=url, params={
                        'formats': [ 'markdown', 'links' ],
                        'excludeTags': [ '.ad', 'script', '#footer' ]
                    })
                    md = response.get('markdown').replace("\\n", " ").replace("\\", "")
                    data = json.loads(repair_json(md))
                    if data:
                        hf_paper_dicts = []
                        for item in data:
                            paper_metadata = item.get('paper')
                            rvsd_paper_metadata = {{'\\_id':'_id'}.get(key, key): 
                                                value for key, value in paper_metadata.items()}
                            hf_paper_dicts.append(rvsd_paper_metadata)
                        return hf_paper_dicts
                    else:
                        return []
                except Exception as e:
                    print(f"Unexpected error: {e}")
                    return []
            else:
                print("Please provide FireCraw API Key for further search.\n")
                return []
        except Exception as e:
            print(f"Unexpected error: {e}")
            return []
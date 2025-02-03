import requests
from datetime import datetime, timezone

class HuggingFaceKit:
    def __init__(self):
        self.base_url = "https://huggingface.co/api/daily_papers"
        self.headers = {}

    def fetch_daily_papers(self, max_cnt=100):
        try:
            response = requests.get(self.base_url)
            # response = requests.get(f"{self.base_url}?limit={max_cnt}")
            response.raise_for_status()
            data = response.json()

            if not data:
                print("No data received from API.")

            # Debug: Print keys of the first paper
            print("Keys in the first paper:", data[0].keys())
            hf_paper_dicts = [item.get('paper') for item in data]
            return hf_paper_dicts
        except requests.RequestException as e:
            print(f"Error fetching papers: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error: {e}")
            return []
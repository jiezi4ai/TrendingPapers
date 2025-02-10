# to-do: 
# 1. add papers from https://paperswithcode.com/
# 2. add papers from https://trendingpapers.com/
import re
import json

from trendingpapers.config import CONFIG
from trendingpapers.tools.github_tool import GitHubKit
from trendingpapers.tools.huggingface_tool import HuggingFaceKit

class PapersRecommended:
    def __init__(self, firecrawl_api_key=None):
        self.github_repo_url = "https://github.com/dair-ai/ML-Papers-of-the-Week"
        self.hugginface_url = "https://huggingface.co/api/daily_papers"
        self.firecrawl_api_key = firecrawl_api_key

    def get_github_recommended_papers(self):
        """Get github recommended papers from url
        """
        github = GitHubKit()
        readme = github.get_repo_readme(self.github_repo_url)

        def extract_paper_info(markdown_text):
            """
            Extracts paper information from a Markdown table and returns it as a JSON array.
            Args:
                markdown_text: The Markdown text containing the table.
            Returns:
                A JSON string representing an array of paper information.
            """
            # Extract paper entries using regex
            paper_entries = re.findall(r"^\s*\| (\d+)\) \*\*([^*]+)\*\* - (.*?)\s*\|\s*\[Paper\]\(([^)]+)\)(?:,\s*\[Tweet\]\(([^)]+)\))?\s*\|", markdown_text, re.MULTILINE)
            papers = []
            for entry in paper_entries:
                paper_info = {
                    "title": entry[1].strip(),
                    "abstract": entry[2].strip(),
                    "paper_url": entry[3].strip(),
                    "tweet_url": entry[4].strip() if entry[4] else None,
                    "description": None,
                    "source": "github",
                    "source_url": self.github_repo_url,
                    "extra_info": None
                }
                papers.append(paper_info)
            return json.dumps(papers, indent=2)

        papers = json.loads(extract_paper_info(readme))
        return papers

    def get_huggingface_daily_papers(self):
        huggingface = HuggingFaceKit(max_retries_cnt=3, firecrawl_api_key=self.firecrawl_api_key)
        hf_papers = huggingface.fetch_daily_papers(max_cnt=100)

        papers = []
        for item in hf_papers:
            if bool(re.match(r"^\d{4}\.\d{5}$", item.get('id'))) == True:
                url = f"https://arxiv.org/abs/{item.get('id')}" 
            else:
                url = None
            paper = {
                "title": item.get('title').replace("\n", ""),
                "abstract": item.get('summary').replace("\n", " "),
                "paper_url": url,
                "tweet_url": None,
                "description": None,
                "source": "huggingface",
                "source_url": self.hugginface_url,
                "extra_info": item
            }
            papers.append(paper)
        return papers
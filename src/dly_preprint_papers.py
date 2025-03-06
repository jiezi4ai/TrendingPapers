import time
from typing import List, Dict

from tools.arxiv_tool import ArxivKit

class PapersPreprint:
    def __init__(self, data_path):
        self.data_path = data_path
        self.arxiv = ArxivKit(self.data_path)
    
    async def pull_arxiv_metadata(
            self,
            domains: List[str], 
            from_date: str,   # date in "yyyy-mm-dd" format
            until_date: str,  # keep date length within 30 days to avoid rate limit
            ) -> List[Dict]:
        """pull arxiv metadata by domain"""
        daily_papers_metadata = []
        for domain in domains:
            # get papers metadata
            papers_metadata = await self.arxiv.retrieve_metadata_by_category(
                category=domain, 
                from_date=from_date, 
                until_date=until_date)
            daily_papers_metadata.extend(papers_metadata)
            time.sleep(10)
        return daily_papers_metadata
    
    def filter_by_category(
            self, 
            paper_metadata: List[Dict], 
            categories: List[str]) -> List[Dict]:
        """further filter papers by category
        Args:
            categories: list of categories, which could be found from https://arxiv.org/category_taxonomy
            paper_metadata: list of paper metadata 
        """
        filtered_papers_metadata = []
        for paper in paper_metadata:
            paper_belongto = paper.get('categories')  # here is a list
            if bool(set(paper_belongto) & set(categories)):
                filtered_papers_metadata.append(paper)
        return filtered_papers_metadata


import arxiv # pip install arxiv (source from https://github.com/lukasschwab/arxiv.py)
from sickle import Sickle # pip install sickle https://github.com/mloesch/sickle

import os
import aiofiles
import aiofiles.os
import aiofiles.ospath
import pandas as pd
from requests.exceptions import HTTPError, RequestException

import asyncio
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def handle_http_error(e):
    """Handle HTTP errors during metadata download."""
    if e.response.status_code == 503:
        retry_after = e.response.headers.get('Retry-After', 30)
        logger.warning(f"HTTPError 503: Server busy. Retrying after {retry_after} seconds.")
        await asyncio.sleep(int(retry_after))
    else:
        logger.error(f'HTTPError: Status code {e.response.status_code}')
        raise e

class ArxivKit:   
    def __init__(self):                 
        self.client = arxiv.Client(page_size= 100, delay_seconds=3.0, num_retries=3)
        self.connection = Sickle('http://export.arxiv.org/oai2')

    def retrieve_metadata_by_paper(
            self,
            query_term: str = '', 
            paper_ids: List = [], 
            max_cnt: int =100, 
            sort_by: str ="relevance",
            order: str = "descending"):
        """search papers' metadata from arxiv
        Args:
            query_term (str): The query term to search for.
            paper_ids (list): The list of paper ids to search for.
        Returns:

        """
        # Construct the default API client.
        if max_cnt > 100:
            self.client = arxiv.Client(page_size=1000, delay_seconds=10.0, num_retries = 5)

        sort_criteria = arxiv.SortCriterion.Relevance
        if sort_by == "lastUpdatedDate":
            sort_criteria = arxiv.SortCriterion.LastUpdatedDate
        elif sort_by == "submittedDate":
            sort_criteria = arxiv.SortCriterion.SubmittedDate

        order_sequence = arxiv.SortOrder.Descending
        if order == "ascending":
            order_sequence = arxiv.SortOrder.Ascending

        # conduct search
        search = arxiv.Search(
            query = query_term,
            id_list = paper_ids,
            max_results = max_cnt,
            sort_by = sort_criteria,
            sort_order = order_sequence
        )
        arxiv_metadata = []
        for item in self.client.results(search):
            arxiv_metadata.append(item.__dict__['_raw'])
        return arxiv_metadata

    async def download_category_metadata(
            self,
            category,
            from_date,
            until_date,
            data_path):
        """Download metadata from arXiv for specific category and date range in batch.
        Args:
            category (str): Specify paper category like "cs", "math", etc.
                Reference to category could be found in http://export.arxiv.org/oai2?verb=ListSets
                Only accept one category at a time.
            from_date (str): The start date for the date range in ReactNative-MM-DD format.
            until_date (str): The end date for the date range in ReactNative-MM-DD format.
        Returns:
            Downloaded xml file with arxiv metadata.
        Note:
            Function originated from jack-tol's [arXivGPT](https://github.com/jack-tol/arXivGPT/blob/main/metadata_pipeline.py).
            With minor modification to: 1. specify paper category (the setSpec param); 2. save one record per line.
        """
        logger.info('Getting papers...')
        params = {'metadataPrefix': 'arXiv',
                'set': category,   # modification 1: add set para to specify paper category
                'from': from_date,
                'until': until_date,
                'ignore_deleted': True}
        data = self.connection.ListRecords(**params)
        logger.info('Papers retrieved.')

        iters = 0
        errors = 0

        xml_file_nm = f"{category}_{from_date}_{until_date}.xml"
        full_path = os.path.join(data_path, xml_file_nm)
        async with aiofiles.open(full_path, 'a+', encoding="utf-8") as f:
            while True:
                try:
                    record = await asyncio.to_thread(lambda: next(data, None))
                    if record is None:
                        logger.info(f'{category} Metadata for the specified period, {from_date} - {until_date} downloaded.')
                        # Check if the file is empty
                        if os.stat(full_path).st_size == 0:
                            logger.warning("No records found matching the criteria.")
                            return None  # Or raise a custom exception: raise NoRecordsFoundError()
                        return full_path  # Return full_path even if no records are found
                    cleaned_record = record.raw.replace('\n', ' ').replace('\r', ' ')  # modification 2: replace multi-line text to one line
                    await f.write(cleaned_record)
                    await f.write('\n')
                    errors = 0
                    iters += 1
                    if iters % 1000 == 0:
                        logger.info(f'{iters} processing attempts made successfully.')

                except HTTPError as e:
                    await handle_http_error(e)

                except RequestException as e:
                    logger.error(f'RequestException: {e}')
                    raise

                except Exception as e:
                    errors += 1
                    logger.error(f'Unexpected error: {e}')
                    if errors > 5:
                        logger.critical('Too many consecutive errors, stopping the harvester.')
                        raise

    async def retrieve_metadata_by_category(self, category, from_date, until_date, data_path):
        """retrieve metadata by category through OAI protocol
        Args:
            category (str): Specify paper category like "cs", "math", etc. 
                Reference to category could be found in http://export.arxiv.org/oai2?verb=ListSets
                Only accept one category at a time.
            from_date (str): The start date for the date range in YYYY-MM-DD format.
            until_date (str): The end date for the date range in YYYY-MM-DD format.
        Returns:
            str: full path of the downloaded metadata file
        """
        full_path = await self.download_category_metadata(category, from_date, until_date, data_path)
        if os.path.exists(full_path) and full_path.endswith('.xml') and os.path.getsize(full_path) > 0:
            # define namespace
            namespaces = {
                'oai': 'http://www.openarchives.org/OAI/2.0/',
                'arxiv': 'http://arxiv.org/OAI/arXiv/'
            }

            oai_metadata = []
            # read xml file by line
            with open(full_path, 'r', encoding='utf-8') as file:
                for line in file:
                    xml_info = ET.fromstring(line)
                
                    # target on record element
                    if xml_info.tag == '{http://www.openarchives.org/OAI/2.0/}record':
                        # get header info
                        header = xml_info.find('oai:header', namespaces)
                        identifier = header.find('oai:identifier', namespaces).text
                        datestamp = header.find('oai:datestamp', namespaces).text
                        setSpec = header.find('oai:setSpec', namespaces).text

                        # get metadata
                        metadata = xml_info.find('oai:metadata', namespaces)
                        arxiv = metadata.find('arxiv:arXiv', namespaces)
                        
                        # get arXiv info
                        arxiv_id = arxiv.find('arxiv:id', namespaces).text
                        created = arxiv.find('arxiv:created', namespaces).text
                        updated = arxiv.find('arxiv:updated', namespaces).text if arxiv.find('arxiv:updated', namespaces) is not None else None
                        
                        # get authors info
                        authors = []
                        for author in arxiv.findall('arxiv:authors/arxiv:author', namespaces):
                            keyname = author.find('arxiv:keyname', namespaces).text
                            forenames = author.find('arxiv:forenames', namespaces).text if author.find('arxiv:forenames', namespaces) is not None else ''
                            suffix = author.find('arxiv:suffix', namespaces)
                            suffix_text = suffix.text if suffix is not None else ''
                            authors.append(f"{forenames} {keyname} {suffix_text}".strip())
                        
                        # get title, abstract, etc
                        title = arxiv.find('arxiv:title', namespaces).text
                        categories = arxiv.find('arxiv:categories', namespaces).text.split(' ')
                        comments = arxiv.find('arxiv:comments', namespaces).text if arxiv.find('arxiv:comments', namespaces) is not None else None
                        journal_ref = arxiv.find('arxiv:journal-ref', namespaces)
                        journal_ref_text = journal_ref.text if journal_ref is not None else None
                        doi = arxiv.find('arxiv:doi', namespaces)
                        doi_text = doi.text if doi is not None else None
                        license = arxiv.find('arxiv:license', namespaces).text
                        abstract = arxiv.find('arxiv:abstract', namespaces).text

                        # construct dict
                        record_data = {
                            "identifier": identifier,
                            "datestamp": datestamp,
                            "setSpec": setSpec,
                            "arxiv_id": arxiv_id,
                            "created": created,
                            "updated": updated,
                            "authors": authors,
                            "title": title,
                            "categories": categories,
                            "comments": comments,
                            "journal_ref": journal_ref_text,
                            "doi": doi_text,
                            "license": license,
                            "abstract": abstract
                        }
                        oai_metadata.append(record_data)
        else:
            logger.error(f'Unexpected error: Failed to download metadata for category {category} from {from_date} to {until_date}.')
            raise

        return oai_metadata
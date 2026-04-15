import arxiv
import os
import time
import logging
from dataclasses import dataclass
from typing import List, Optional

from config import PDF_STORAGE_PATH, MAX_PAPERS_PER_SEARCH



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# __name__ is the current file's module name (pipeline.arxiv_fetcher)
# This means log messages will show which file they came from.

# ── Data Structure ────────────────────────────────────────────────────
@dataclass
class Paper:
    """
    Represents a single research paper fetched from ArXiv.

    @dataclass automatically generates __init__, __repr__, and
    __eq__ methods based on the fields defined below.
    Without @dataclass, you'd have to write all of that manually.
    """
    paper_id: str        # ArXiv unique ID e.g. "2401.12345"
    title: str           # Full paper title
    authors: List[str]   # List of author names
    abstract: str        # Paper summary/abstract
    published: str       # Publication date as string
    pdf_url: str         # Direct URL to download the PDF
    local_pdf_path: Optional[str] = None  # Path after we download it
    # Optional[str] means this can be either a string OR None.
    # It starts as None because we haven't downloaded it yet.

# ── Main Fetcher Class ────────────────────────────────────────────────
class ArXivFetcher:
    """
    Handles searching ArXiv and downloading papers.

    We use a class here (not just functions) because:
    1. It groups related functionality together
    2. It can hold state (like the storage path)
    3. It's easier to test and mock in unit tests
    """

    def __init__(self, storage_path: str = PDF_STORAGE_PATH):
        """
        Called automatically when you create an ArXivFetcher object.

        storage_path: where to save downloaded PDFs
        """
        self.storage_path = storage_path
        self.client = arxiv.Client()
        # arxiv.Client() is the official ArXiv API client.
        # We create it once here and reuse it for all searches.
        # Creating it once (not every search) is more efficient.

        # Create the storage directory if it doesn't exist
        os.makedirs(self.storage_path, exist_ok=True)
        # exist_ok=True means: if the folder already exists,
        # don't raise an error — just continue silently.

    def search_papers(
        self,
        query: str,
        max_results: int = MAX_PAPERS_PER_SEARCH
    ) -> List[Paper]:
        """
        Search ArXiv for papers matching a query.

        query: the search string e.g. "transformer drug discovery"
        max_results: how many papers to return (default from config)

        Returns: a list of Paper objects
        """
        logger.info(f"🔍 Searching ArXiv for: '{query}'")

        # ── Build the search ──────────────────────────────────────
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
            # SortCriterion.Relevance → most relevant papers first
            # Alternative: SortCriterion.SubmittedDate → newest first
            # For research gaps, relevance is more useful than recency
        )

        # ── Execute and collect results ───────────────────────────
        papers = []

        for result in self.client.results(search):
            # result is one ArXiv paper returned by the API
            # We convert it into our own Paper dataclass
            # so the rest of our system doesn't depend on
            # ArXiv's specific data format (loose coupling)

            paper = Paper(
                paper_id=result.entry_id.split("/")[-1],
                # entry_id looks like "http://arxiv.org/abs/2401.12345v1"
                # .split("/")[-1] extracts just "2401.12345v1"

                title=result.title.strip(),
                # .strip() removes any leading/trailing whitespace

                authors=[author.name for author in result.authors],
                # result.authors is a list of Author objects
                # We extract just the .name string from each one
                # This is called a list comprehension — a compact
                # way to build a list by transforming another list

                abstract=result.summary.strip(),

                published=str(result.published.date()),
                # result.published is a datetime object
                # .date() extracts just the date part (no time)
                # str() converts it to "2024-01-15" format

                pdf_url=result.pdf_url,
            )
            papers.append(paper)

        logger.info(f"✅ Found {len(papers)} papers")
        return papers

    def download_pdf(self, paper: Paper) -> Optional[str]:
        """
        Downloads a paper's PDF to local storage.

        paper: a Paper object (must have pdf_url and paper_id)
        Returns: the local file path if successful, None if failed
        """
        # Build the filename from the paper ID
        filename = f"{paper.paper_id.replace('/', '_')}.pdf"
        # We replace '/' with '_' because '/' in a filename
        # would be interpreted as a folder separator — bad!

        filepath = os.path.join(self.storage_path, filename)
        # os.path.join safely combines folder + filename
        # On Linux: "data/pdfs/2401.12345v1.pdf"
        # Always use os.path.join instead of string concatenation
        # because it handles OS differences automatically

        # Skip download if we already have this PDF
        if os.path.exists(filepath):
            logger.info(f"📄 PDF already exists: {filename}")
            paper.local_pdf_path = filepath
            return filepath

        try:
            logger.info(f"⬇️  Downloading: {paper.title[:50]}...")
            # [:50] shows only first 50 chars of title (keeps logs clean)

            import urllib.request
            urllib.request.urlretrieve(paper.pdf_url, filepath)
            # urlretrieve downloads a file from a URL and saves it
            # to the specified filepath. Simple and reliable.

            paper.local_pdf_path = filepath
            logger.info(f"✅ Saved to: {filepath}")

            # Be polite to ArXiv's servers — wait between downloads
            time.sleep(1)
            # ArXiv has rate limits. If you download too fast,
            # they'll block your IP. 1 second between downloads
            # is the recommended courtesy delay.

            return filepath

        except Exception as e:
            # If anything goes wrong (network error, disk full, etc.)
            # log the error and return None instead of crashing
            # the entire program. Resilience over perfection.
            logger.error(f"❌ Failed to download {paper.paper_id}: {e}")
            return None

    def fetch_and_download(
        self,
        query: str,
        max_results: int = MAX_PAPERS_PER_SEARCH
    ) -> List[Paper]:
        """
        Convenience method that combines search + download in one call.

        This is the main method agents will call.
        It searches ArXiv, then downloads all found PDFs.

        Returns: list of Paper objects with local_pdf_path filled in
        """
        # Step 1: Search
        papers = self.search_papers(query, max_results)

        # Step 2: Download each paper's PDF
        for paper in papers:
            self.download_pdf(paper)

        # Step 3: Return papers that downloaded successfully
        successful = [p for p in papers if p.local_pdf_path]
        # List comprehension: keep only papers where
        # local_pdf_path is not None (download succeeded)

        logger.info(
            f"📚 Fetch complete: {len(successful)}/{len(papers)} "
            f"papers downloaded successfully"
        )
        return successful
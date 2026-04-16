# pipeline/pdf_parser.py
#
# Extracts plain text from downloaded ArXiv PDF files.
# The text this produces will be fed to the GraphRAG Agent
# in Week 2 so the LLM can extract concepts and relationships.
#
# Flow:
# PDF file on disk → PyMuPDF → raw text per page → cleaned text string

import logging
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF — 'fitz' is the internal module name

logger = logging.getLogger(__name__)


class PDFParser:
    """
    Extracts text content from research paper PDFs.

    Kept as a class (not just a function) so we can
    add configuration later — e.g. max pages to parse,
    or different extraction strategies for different PDF types.
    """

    def __init__(self, max_pages: Optional[int] = None):
        """
        max_pages: if set, only parse the first N pages.
                   Research papers can be 30+ pages — for concept
                   extraction the abstract + intro is often enough.
                   None means parse all pages.
        """
        self.max_pages = max_pages

    def extract_text(self, pdf_path: str) -> Optional[str]:
        """
        Extracts all text from a PDF file.

        pdf_path: full path to the PDF file on disk
        Returns: extracted text as a single string,
                 or None if extraction fails.
        """
        
        if pdf_path is None:
            logger.error("❌ pdf_path is None — PDF was not downloaded")
            return None

        # Validate the file exists before trying to open it
        path = Path(pdf_path)
        # Path() is from Python's pathlib — a cleaner way to
        # work with file paths than raw strings.
        # It works on Windows, Mac, and Linux automatically.

        if not path.exists():
            logger.error(f"❌ PDF not found: {pdf_path}")
            return None

        if not path.suffix == ".pdf":
            logger.error(f"❌ Not a PDF file: {pdf_path}")
            return None

        try:
            return self._extract_with_pymupdf(pdf_path)

        except Exception as e:
            logger.error(f"❌ Failed to parse {pdf_path}: {e}")
            return None

    def _extract_with_pymupdf(self, pdf_path: str) -> str:
        """
        Internal method that does the actual extraction using PyMuPDF.
        """
        extracted_pages = []

        # fitz.open() opens the PDF — like open() for text files
        # but understands PDF structure
        with fitz.open(pdf_path) as doc:
            # doc is the PDF document object
            # It's a context manager — closes automatically

            total_pages = len(doc)
            pages_to_parse = (
                min(self.max_pages, total_pages)
                if self.max_pages
                else total_pages
            )
            # min() picks the smaller of the two values —
            # so if max_pages=10 but PDF has 6 pages, we parse 6.

            logger.info(
                f"📄 Parsing {pages_to_parse}/{total_pages} pages "
                f"from {Path(pdf_path).name}"
            )

            for page_num in range(pages_to_parse):
                page = doc[page_num]
                # doc[page_num] gives you one page object
                # Pages are 0-indexed (first page = doc[0])

                text = page.get_text()
                # get_text() extracts all readable text from that page
                # Returns a string — may include newlines, spaces, etc.

                cleaned = self._clean_text(text)

                if cleaned:
                    extracted_pages.append(cleaned)

        full_text = "\n\n".join(extracted_pages)
        # Join all pages with double newline between them
        # This preserves page boundaries in the output

        logger.info(
            f"✅ Extracted {len(full_text):,} characters "
            f"from {Path(pdf_path).name}"
        )
        # :, formats the number with commas — e.g. 42381 → "42,381"

        return full_text

    def _clean_text(self, raw_text: str) -> str:
        """
        Cleans up raw text extracted from a PDF page.

        PDFs often have:
        - Excessive whitespace and blank lines
        - Hyphenated line breaks (re- \n search → research)
        - Headers/footers repeated on every page

        We do light cleaning here — heavy NLP cleaning
        is the GraphRAG Agent's job.
        """
        if not raw_text or not raw_text.strip():
            return ""
            # strip() removes whitespace from start and end
            # If the page is blank after stripping, skip it

        # Fix hyphenated line breaks
        # PDFs break long words across lines with a hyphen:
        # "trans-\nformer" should become "transformer"
        import re
        text = re.sub(r"-\n", "", raw_text)
        # re.sub(pattern, replacement, string)
        # r"-\n" means: a hyphen followed by a newline
        # Replace with "" (nothing) — joins the word back together

        # Collapse multiple blank lines into one
        text = re.sub(r"\n{3,}", "\n\n", text)
        # \n{3,} means: 3 or more consecutive newlines
        # Replace with \n\n (single blank line)
        # Keeps paragraph structure without excessive gaps

        return text.strip()

    def extract_abstract(self, pdf_path: str) -> Optional[str]:
        """
        Extracts just the first page — usually contains the
        title, authors, and abstract.

        Useful for quick concept extraction without parsing
        the full paper. The Orchestrator Agent will use this
        for initial triage of papers.
        """
        # Temporarily set max_pages to 1
        original_max = self.max_pages
        self.max_pages = 2  # page 0 = title/abstract, page 1 = intro
        
        result = self.extract_text(pdf_path)
        
        self.max_pages = original_max  # restore original setting
        return result
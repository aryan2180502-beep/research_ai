# pipeline/neo4j_ingestor.py
#
# Takes Paper objects fetched from ArXiv and stores them
# permanently in the Neo4j knowledge graph.
#
# Flow:
# Paper object → create Paper node → create Author nodes
#             → create Concept nodes → create relationships

import logging
from typing import List

from graph.connection import Neo4jConnection
from pipeline.arxiv_fetcher import Paper

logger = logging.getLogger(__name__)


class Neo4jIngestor:
    """
    Responsible for writing Paper data into the Neo4j graph.

    Keeps all database write logic in one place —
    if we change the graph schema, we only change this file.
    """

    def __init__(self, connection: Neo4jConnection):
        """
        connection: an active Neo4jConnection object
        We accept it as a parameter (dependency injection)
        rather than creating it internally.

        Why dependency injection?
        - Makes testing easier (pass a mock connection in tests)
        - Enforces single connection across the whole app
        - Caller controls the connection lifecycle
        This is a very common interview topic.
        """
        self.conn = connection

    def ingest_paper(self, paper: Paper) -> bool:
        """
        Saves a single Paper into the knowledge graph.

        Creates:
        - One Paper node
        - One Author node per author
        - AUTHORED relationships (Author → Paper)

        Returns True if successful, False if failed.
        """
        try:
            # ── Step 1: Create the Paper node ─────────────────────
            self._create_paper_node(paper)

            # ── Step 2: Create Author nodes + relationships ────────
            for author_name in paper.authors:
                self._create_author_relationship(paper.paper_id, author_name)

            logger.info(f"✅ Ingested: {paper.title[:60]}...")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to ingest {paper.paper_id}: {e}")
            return False

    def _create_paper_node(self, paper: Paper):
        """
        Creates or updates a Paper node in Neo4j.

        The underscore prefix on _create_paper_node signals
        this is a 'private' method — internal use only.
        Python doesn't enforce this, but it's a strong convention
        that other developers understand and respect.
        """
        query = """
        MERGE (p:Paper {paper_id: $paper_id})
        SET p.title = $title,
            p.abstract = $abstract,
            p.published = $published,
            p.pdf_url = $pdf_url,
            p.local_pdf_path = $local_pdf_path
        """
        # MERGE finds or creates the Paper node by paper_id
        # SET updates all its properties
        # This means running ingest twice won't duplicate data —
        # it just updates the existing node. Idempotent operation.
        # Idempotent = running it multiple times has same effect as once.
        # Very important property in data pipelines.

        self.conn.run_query(query, {
            "paper_id": paper.paper_id,
            "title": paper.title,
            "abstract": paper.abstract,
            "published": paper.published,
            "pdf_url": paper.pdf_url,
            "local_pdf_path": paper.local_pdf_path or ""
            # 'or ""' converts None to empty string
            # Neo4j handles None/null but empty string is cleaner
            # for text properties we'll search later
        })

    def _create_author_relationship(self, paper_id: str, author_name: str):
        """
        Creates an Author node and connects it to a Paper.

        The Cypher here does three things in one query:
        1. Find or create the Paper node
        2. Find or create the Author node
        3. Find or create the AUTHORED relationship between them
        """
        query = """
        MATCH (p:Paper {paper_id: $paper_id})
        MERGE (a:Author {name: $author_name})
        MERGE (a)-[:AUTHORED]->(p)
        """
        # MATCH finds the existing Paper (we just created it)
        # MERGE on Author: create if doesn't exist
        # MERGE on relationship: create if doesn't exist
        # If this author wrote another paper already in our graph,
        # the existing Author node gets a second AUTHORED relationship
        # — exactly what we want

        self.conn.run_query(query, {
            "paper_id": paper_id,
            "author_name": author_name
        })

    # def add_concept_to_paper(self, paper_id: str, concept_name: str):
    #     """
    #     Links a Concept node to a Paper with INTRODUCES relationship.

    #     This will be called by the GraphRAG Agent in Week 2
    #     after it extracts concepts from the paper text using an LLM.
    #     We define it now so the schema is ready.
    #     """
    #     query = """
    #     MATCH (p:Paper {paper_id: $paper_id})
    #     MERGE (c:Concept {name: $concept_name})
    #     MERGE (p)-[:INTRODUCES]->(c)
    #     """
    #     self.conn.run_query(query, {
    #         "paper_id": paper_id,
    #         "concept_name": concept_name
    #     })
    #     logger.info(f"🔗 Linked concept '{concept_name}' to paper {paper_id}")

    def add_concept_to_paper(self, paper_id: str, concept_name: str, summary: str = None):

        """
        Links a Concept node to a Paper with an INTRODUCES relationship.
        The summary (how THIS paper specifically uses/defines the concept)
        is stored on the relationship, not the Concept node — because the
        same Concept node is MERGE'd across many papers, and each paper
        may explain it differently. Storing on the node would let the last
        paper processed silently overwrite every earlier paper's summary.
        """
        
        query = """
        MATCH (p:Paper {paper_id: $paper_id})
        MERGE (c:Concept {name: $concept_name})
        MERGE (p)-[r:INTRODUCES]->(c)
        SET r.summary = $summary
        """
        self.conn.run_query(query, {
            "paper_id": paper_id,
            "concept_name": concept_name,
            "summary": summary
        })
        logger.info(f"🔗 Linked concept '{concept_name}' to paper {paper_id}")

    def link_related_concepts(self, concept_a: str, concept_b: str):
        """
        Creates a RELATED_TO relationship between two concepts.

        This builds the conceptual web in our knowledge graph —
        connecting ideas across different papers.
        The Critic Agent will use this to identify research gaps:
        concepts that appear in many papers = well researched
        concepts with few connections = potential gaps
        """
        query = """
        MERGE (a:Concept {name: $concept_a})
        MERGE (b:Concept {name: $concept_b})
        MERGE (a)-[:RELATED_TO]->(b)
        """
        self.conn.run_query(query, {
            "concept_a": concept_a,
            "concept_b": concept_b
        })

    def ingest_papers(self, papers: List[Paper]) -> dict:
        """
        Ingests a list of papers and returns a summary report.

        This is the main method the agents will call —
        pass a whole batch of papers, get back a summary.
        """
        logger.info(f"📥 Starting ingestion of {len(papers)} papers...")

        successful = 0
        failed = 0

        for paper in papers:
            if self.ingest_paper(paper):
                successful += 1
            else:
                failed += 1

        # Build a summary report
        report = {
            "total": len(papers),
            "successful": successful,
            "failed": failed,
            "success_rate": f"{(successful/len(papers)*100):.1f}%"
            # :.1f formats the float to 1 decimal place
            # e.g. 66.666... becomes "66.7%"
        }

        logger.info(f"📊 Ingestion complete: {report}")
        return report

    def get_graph_stats(self) -> dict:
        """
        Returns statistics about what's currently in the graph.

        Useful for debugging and for the Orchestrator agent
        to understand how much data is available.
        """
        stats = {}

        # Count each node type
        for label in ["Paper", "Author", "Concept"]:
            result = self.conn.run_query(
                f"MATCH (n:{label}) RETURN count(n) AS count"
            )
            stats[label.lower() + "s"] = result[0]["count"]
            # e.g. "papers": 42, "authors": 156, "concepts": 89

        # Count relationships
        result = self.conn.run_query(
            "MATCH ()-[r]->() RETURN count(r) AS count"
        )
        # ()-[r]->() means: any node, any relationship, any node
        # This counts ALL relationships in the graph
        stats["relationships"] = result[0]["count"]

        return stats
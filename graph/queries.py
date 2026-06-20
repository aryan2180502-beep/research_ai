# graph/queries.py

import logging
from graph.connection import Neo4jConnection

logger = logging.getLogger(__name__)


def get_all_concepts(conn: Neo4jConnection) -> list[str]:
    """Returns every concept node name in the graph."""
    result = conn.run_query("MATCH (c:Concept) RETURN c.name AS name")
    return [row["name"] for row in result]


def get_concepts_for_paper(conn: Neo4jConnection, paper_id: str) -> list[str]:
    """Returns all concepts linked to a specific paper."""
    result = conn.run_query(
        """
        MATCH (p:Paper {paper_id: $paper_id})-[:INTRODUCES]->(c:Concept)
        RETURN c.name AS name
        """,
        parameters={"paper_id": paper_id},
    )
    return [row["name"] for row in result]


def get_related_concepts(conn: Neo4jConnection, concept_name: str) -> list[str]:
    """Returns concepts directly related to the given concept."""
    result = conn.run_query(
        """
        MATCH (a:Concept {name: $name})-[:RELATED_TO]-(b:Concept)
        RETURN DISTINCT b.name AS name
        """,
        parameters={"name": concept_name},
    )
    return [row["name"] for row in result]


def get_papers_by_concept(conn: Neo4jConnection, concept_name: str) -> list[dict]:
    """Returns all papers that mention a given concept."""
    result = conn.run_query(
        """
        MATCH (p:Paper)-[:INTRODUCES]->(c:Concept {name: $name})
        RETURN p.paper_id AS paper_id, p.title AS title
        """,
        parameters={"name": concept_name},
    )
    return [dict(row) for row in result]


def find_research_gaps(conn: Neo4jConnection, min_papers: int = 2) -> list[dict]:
    """
    Finds concepts that appear in multiple papers but have
    NO relationships to other concepts — potential research gaps.
    """
    result = conn.run_query(
        """
        MATCH (c:Concept)<-[:INTRODUCES]-(p:Paper)
        WITH c, COUNT(p) AS paper_count
        WHERE paper_count >= $min_papers
          AND NOT (c)-[:RELATED_TO]-()
        RETURN c.name AS concept, paper_count
        ORDER BY paper_count DESC
        """,
        parameters={"min_papers": min_papers},
    )
    return [dict(row) for row in result]


def get_most_connected_concepts(conn: Neo4jConnection, top_n: int = 10) -> list[dict]:
    """Returns the most connected concepts — the 'hubs' of your knowledge graph."""
    result = conn.run_query(
        """
        MATCH (c:Concept)-[:RELATED_TO]-()
        RETURN c.name AS concept, COUNT(*) AS connections
        ORDER BY connections DESC
        LIMIT $top_n
        """,
        parameters={"top_n": top_n},
    )
    return [dict(row) for row in result]


def get_graph_summary(conn: Neo4jConnection) -> dict:
    """
    High-level stats — used by orchestrator for reporting.
    
    Refactored to use OPTIONAL MATCH for robustness:
    - Each count is independent (no cascading failures)
    - Returns zeros gracefully if no nodes of a type exist
    - Cleaner, more maintainable than chained WITH clauses
    """
    result = conn.run_query(
        """
        OPTIONAL MATCH (p:Paper) WITH COUNT(p) AS papers
        OPTIONAL MATCH (c:Concept) WITH papers, COUNT(c) AS concepts
        OPTIONAL MATCH ()-[r:RELATED_TO]->() WITH papers, concepts, COUNT(r) AS relationships
        RETURN papers, concepts, relationships
        """
    )
    if result:
        return dict(result[0])
    return {"papers": 0, "concepts": 0, "relationships": 0}

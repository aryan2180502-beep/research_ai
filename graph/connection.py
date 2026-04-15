# graph/connection.py
#
# Manages the single Neo4j database connection for the entire app.
# All other files import from here — nobody creates their own connection.

import logging
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

logger = logging.getLogger(__name__)


class Neo4jConnection:
    """
    Manages a single connection to Neo4j.

    This class follows the Singleton-like pattern —
    create it once, pass it around, close it at the end.
    """

    def __init__(
        self,
        uri: str = NEO4J_URI,
        username: str = NEO4J_USERNAME,
        password: str = NEO4J_PASSWORD
    ):
        """
        Opens the connection to Neo4j when this object is created.
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        # driver is Neo4j's term for the connection object.
        # It starts as None — we'll set it in connect()

        self.connect()

    def connect(self):
        """
        Actually opens the connection to Neo4j.
        Separated from __init__ so we can reconnect if needed.
        """
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            # GraphDatabase.driver() creates the connection.
            # auth= takes a tuple of (username, password).
            # This doesn't actually send a query yet —
            # it just sets up the connection channel.

            # Verify the connection actually works
            self.driver.verify_connectivity()
            # verify_connectivity() sends a small test ping
            # to Neo4j. If Neo4j isn't running or the password
            # is wrong, this raises an exception immediately.
            # Better to fail here than during an agent run.

            logger.info("✅ Connected to Neo4j successfully")

        except AuthError:
            # AuthError = wrong username or password
            logger.error("❌ Neo4j authentication failed — check NEO4J_USERNAME and NEO4J_PASSWORD in .env")
            raise

        except ServiceUnavailable:
            # ServiceUnavailable = Neo4j isn't running
            logger.error("❌ Neo4j is not running — start it with: docker start researchpilot-neo4j")
            raise

    def get_session(self):
        """
        Returns a Neo4j session for running queries.

        A session is like a single conversation with Neo4j.
        You run queries inside a session, then close it.
        The driver manages a pool of sessions automatically.
        """
        return self.driver.session()

    def run_query(self, query: str, parameters: dict = None):
        """
        Runs a Cypher query and returns the results.

        query: the Cypher query string
        parameters: optional dict of values to inject safely
                   (prevents injection attacks — like SQL injection
                   but for graph databases)

        Returns: list of result records
        """
        with self.get_session() as session:
            # 'with' statement automatically closes the session
            # when the block ends — even if an error occurs.
            # This is called a context manager.

            result = session.run(query, parameters or {})
            # parameters or {} means: if parameters is None,
            # use an empty dict instead. Safe default.

            return [record for record in result]
            # Convert the result cursor to a plain list.
            # The cursor expires after the session closes,
            # so we collect all records before that happens.

    def close(self):
        """
        Closes the connection cleanly.
        Always call this when your app shuts down.
        """
        if self.driver:
            self.driver.close()
            logger.info("🔌 Neo4j connection closed")


# ── Knowledge Graph Schema ────────────────────────────────────────────
def create_schema(conn: Neo4jConnection):
    """
    Creates the graph schema — nodes and relationships
    that ResearchPilot will use.

    Think of this like CREATE TABLE in SQL, but for a graph.
    Run this once when setting up the project.
    """

    logger.info("📐 Creating knowledge graph schema...")

    # ── Constraints ───────────────────────────────────────────────
    # Constraints ensure data integrity — like PRIMARY KEY in SQL.
    # UNIQUE constraint = no two nodes of this type can have
    # the same value for this property.

    constraints = [
        # Each paper has a unique ArXiv ID
        """
        CREATE CONSTRAINT paper_id_unique IF NOT EXISTS
        FOR (p:Paper) REQUIRE p.paper_id IS UNIQUE
        """,

        # Each author has a unique name
        # (simplified — real systems would use author IDs)
        """
        CREATE CONSTRAINT author_name_unique IF NOT EXISTS
        FOR (a:Author) REQUIRE a.name IS UNIQUE
        """,

        # Each concept has a unique name
        """
        CREATE CONSTRAINT concept_name_unique IF NOT EXISTS
        FOR (c:Concept) REQUIRE c.name IS UNIQUE
        """,
    ]

    for constraint in constraints:
        conn.run_query(constraint)

    # ── Indexes ───────────────────────────────────────────────────
    # Indexes speed up lookups — like an index in a book.
    # Without an index, Neo4j scans every node to find matches.
    # With an index, it jumps directly to the right nodes.

    indexes = [
        # Speed up paper searches by title
        """
        CREATE INDEX paper_title_index IF NOT EXISTS
        FOR (p:Paper) ON (p.title)
        """,

        # Speed up paper searches by date
        """
        CREATE INDEX paper_published_index IF NOT EXISTS
        FOR (p:Paper) ON (p.published)
        """,

        # Speed up concept lookups by name
        """
        CREATE INDEX concept_name_index IF NOT EXISTS
        FOR (c:Concept) ON (c.name)
        """,
    ]

    for index in indexes:
        conn.run_query(index)

    logger.info("✅ Schema created successfully")
    logger.info("")
    logger.info("📊 Graph structure:")
    logger.info("   Nodes    : Paper, Author, Concept")
    logger.info("   Relationships:")
    logger.info("   (Author)-[:AUTHORED]->(Paper)")
    logger.info("   (Paper)-[:INTRODUCES]->(Concept)")
    logger.info("   (Paper)-[:CITES]->(Paper)")
    logger.info("   (Concept)-[:RELATED_TO]->(Concept)")
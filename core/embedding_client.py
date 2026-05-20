"""
Embedding Client — Interface to Modal embeddings service.
Handles local caching and sqlite-vec integration for similarity search.
"""
import json
import sqlite3
import numpy as np
from pathlib import Path
from typing import Optional
import modal

from config.settings import DB_PATH, DATA_DIR


class EmbeddingClient:
    """
    Client for querying Modal embedding service.
    Falls back to local cache when available.
    """

    def __init__(self):
        self._app = None
        self._service = None
        self._connect()

    def _connect(self):
        """Connect to Modal app."""
        try:
            self._app = modal.App.lookup("cris-embeddings", create_if_missing=False)
            self._service = modal.Cls.lookup("cris-embeddings", "EmbedService")()
            print("[embed_client] Connected to Modal embeddings service")
        except Exception as e:
            print(f"[embed_client] Could not connect to Modal: {e}")
            self._app = None
            self._service = None

    def is_available(self) -> bool:
        """Check if embedding service is available."""
        return self._service is not None

    async def embed_text(self, text: str) -> list[float]:
        """Embed single text. Returns 2560-dim float list."""
        if not self._service:
            raise RuntimeError("Embedding service not available")
        return self._service.embed_text.remote(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts efficiently."""
        if not self._service:
            raise RuntimeError("Embedding service not available")
        return self._service.embed_batch.remote(texts)

    async def similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity."""
        if not self._service:
            raise RuntimeError("Embedding service not available")
        return self._service.similarity.remote(text1, text2)

    async def find_cross_domain_connections(
        self,
        source_text: str,
        candidates: list[dict],
        top_k: int = 10,
    ) -> list[dict]:
        """
        Find semantically similar papers across domains.

        Args:
            source_text: Source paper abstract or query
            candidates: List of {id, text, domain} dicts
            top_k: Number of top matches to return

        Returns:
            Sorted list of {id, domain, similarity} dicts
        """
        if not self._service:
            raise RuntimeError("Embedding service not available")

        results = self._service.cross_domain_similarity.remote(source_text, candidates)
        return results[:top_k]


class EmbeddingStore:
    """
    Local storage for embeddings using sqlite-vec extension.
    Falls back to JSON files if extension not available.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._vec_available = self._check_vec_extension()
        self._init_tables()

    def _check_vec_extension(self) -> bool:
        """Check if sqlite-vec extension is available."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("SELECT load_extension('vec0')")
            conn.close()
            return True
        except Exception:
            return False

    def _init_tables(self):
        """Initialize embedding tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Metadata table (always works)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_embeddings (
                arxiv_id TEXT PRIMARY KEY,
                has_embedding BOOLEAN DEFAULT 0,
                embedding_dim INTEGER DEFAULT 2560,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Check if we need to create vec0 table
        if self._vec_available:
            try:
                cursor.execute("SELECT load_extension('vec0')")
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS paper_vectors USING vec0(
                        arxiv_id TEXT PRIMARY KEY,
                        embedding float[2560]
                    )
                """)
                print("[embed_store] Using sqlite-vec for fast similarity search")
            except Exception as e:
                print(f"[embed_store] Could not create vec0 table: {e}")
                self._vec_available = False

        conn.commit()
        conn.close()

    async def store_embedding(self, arxiv_id: str, embedding: list[float]):
        """Store embedding for a paper."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Store metadata
            cursor.execute("""
                INSERT OR REPLACE INTO paper_embeddings (arxiv_id, has_embedding, embedding_dim)
                VALUES (?, 1, ?)
            """, (arxiv_id, len(embedding)))

            # Store in vec0 if available
            if self._vec_available:
                cursor.execute("SELECT load_extension('vec0')")
                cursor.execute("""
                    INSERT OR REPLACE INTO paper_vectors (arxiv_id, embedding)
                    VALUES (?, ?)
                """, (arxiv_id, json.dumps(embedding)))
            else:
                # Fallback: store in separate file
                vector_file = DATA_DIR / "vectors" / f"{arxiv_id}.json"
                vector_file.parent.mkdir(parents=True, exist_ok=True)
                with open(vector_file, "w") as f:
                    json.dump({"arxiv_id": arxiv_id, "embedding": embedding}, f)

            conn.commit()
        except Exception as e:
            print(f"[embed_store] Error storing embedding for {arxiv_id}: {e}")
        finally:
            conn.close()

    async def get_embedding(self, arxiv_id: str) -> Optional[list[float]]:
        """Retrieve embedding for a paper."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            if self._vec_available:
                cursor.execute("SELECT load_extension('vec0')")
                cursor.execute("""
                    SELECT embedding FROM paper_vectors WHERE arxiv_id = ?
                """, (arxiv_id,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
            else:
                # Fallback from file
                vector_file = DATA_DIR / "vectors" / f"{arxiv_id}.json"
                if vector_file.exists():
                    with open(vector_file) as f:
                        data = json.load(f)
                        return data.get("embedding")
            return None
        except Exception as e:
            print(f"[embed_store] Error retrieving embedding for {arxiv_id}: {e}")
            return None
        finally:
            conn.close()

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 20,
        ) -> list[dict]:
        """
        Find similar papers using cosine similarity.

        Args:
            query_embedding: Query vector (2560-dim)
            top_k: Number of results to return

        Returns:
            List of {arxiv_id, similarity} dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        results = []

        try:
            if self._vec_available:
                # Use sqlite-vec for fast search
                cursor.execute("SELECT load_extension('vec0')")
                cursor.execute("""
                    SELECT arxiv_id, vec_distance_cosine(embedding, ?) as dist
                    FROM paper_vectors
                    ORDER BY dist
                    LIMIT ?
                """, (json.dumps(query_embedding), top_k))

                for row in cursor.fetchall():
                    # Convert distance to similarity (cosine distance = 1 - similarity)
                    similarity = 1 - row[1]
                    results.append({"arxiv_id": row[0], "similarity": similarity})
            else:
                # Brute force fallback
                query_vec = np.array(query_embedding)
                query_norm = np.linalg.norm(query_vec)

                # Get all embeddings
                cursor.execute("SELECT arxiv_id FROM paper_embeddings WHERE has_embedding = 1")
                arxiv_ids = [row[0] for row in cursor.fetchall()]

                similarities = []
                for arxiv_id in arxiv_ids:
                    vector_file = DATA_DIR / "vectors" / f"{arxiv_id}.json"
                    if vector_file.exists():
                        with open(vector_file) as f:
                            data = json.load(f)
                            vec = np.array(data["embedding"])
                            vec_norm = np.linalg.norm(vec)
                            sim = np.dot(query_vec, vec) / (query_norm * vec_norm)
                            similarities.append((arxiv_id, float(sim)))

                similarities.sort(key=lambda x: x[1], reverse=True)
                results = [{"arxiv_id": vid, "similarity": sim} for vid, sim in similarities[:top_k]]

        except Exception as e:
            print(f"[embed_store] Similarity search error: {e}")
        finally:
            conn.close()

        return results


class HybridSearchEngine:
    """
    Combines BM25 (FTS5) with semantic (embedding) search.
    Provides cross-domain discovery capabilities.
    """

    def __init__(self):
        from core.search_engine import search as bm25_search
        self.bm25_search = bm25_search
        self.embed_client = EmbeddingClient()
        self.embed_store = EmbeddingStore()

    async def hybrid_search(
        self,
        query: str,
        limit: int = 20,
        alpha: float = 0.5,
    ) -> list[dict]:
        """
        Hybrid search: BM25 + cosine similarity.

        Args:
            query: Search query
            limit: Max results
            alpha: Weight for semantic (0 = BM25 only, 1 = semantic only)

        Returns:
            Reranked results
        """
        # Get BM25 results
        bm25_results = self.bm25_search(query, limit=limit * 2)

        if not self.embed_client.is_available() or alpha == 0:
            return bm25_results[:limit]

        # Get query embedding
        try:
            query_embedding = await self.embed_client.embed_text(query)
        except Exception as e:
            print(f"[hybrid] Embedding failed: {e}")
            return bm25_results[:limit]

        # Get embeddings for results (from cache or compute)
        arxiv_ids = [r["arxiv_id"] for r in bm25_results]
        embeddings = {}

        for arxiv_id in arxiv_ids:
            cached = await self.embed_store.get_embedding(arxiv_id)
            if cached:
                embeddings[arxiv_id] = cached

        # Compute similarity scores
        query_vec = np.array(query_embedding)
        query_norm = np.linalg.norm(query_vec)

        combined_scores = []
        for i, result in enumerate(bm25_results):
            arxiv_id = result["arxiv_id"]

            # BM25 score (normalized rank)
            bm25_score = 1.0 - (i / len(bm25_results))  # Higher rank = higher score

            # Semantic score
            semantic_score = 0.0
            if arxiv_id in embeddings:
                vec = np.array(embeddings[arxiv_id])
                vec_norm = np.linalg.norm(vec)
                if vec_norm > 0:
                    semantic_score = np.dot(query_vec, vec) / (query_norm * vec_norm)

            # Combined score
            combined = (1 - alpha) * bm25_score + alpha * semantic_score

            result["bm25_score"] = bm25_score
            result["semantic_score"] = semantic_score
            result["combined_score"] = combined
            combined_scores.append(result)

        # Sort by combined score
        combined_scores.sort(key=lambda x: x["combined_score"], reverse=True)
        return combined_scores[:limit]

    async def cross_domain_discovery(
        self,
        arxiv_id: str,
        source_domain: str,
        target_domains: list[str],
        top_k: int = 10,
    ) -> list[dict]:
        """
        Find papers in target domains similar to source paper.
        This is the core cross-domain research intelligence feature.

        Args:
            arxiv_id: Source paper ID
            source_domain: Domain of source paper
            target_domains: Domains to search in
            top_k: Number of top connections

        Returns:
            List of {arxiv_id, title, domain, similarity, mechanism} dicts
        """
        if not self.embed_client.is_available():
            return {"error": "Embedding service not available", "connections": []}

        # Get source paper
        from core.domain_manager import get_paper_by_id
        source_paper = get_paper_by_id(arxiv_id)
        if not source_paper:
            return {"error": "Source paper not found", "connections": []}

        source_text = f"{source_paper.get('title', '')} {source_paper.get('abstract', '')}"

        # Gather candidates from target domains
        from core.search_engine import search
        candidates = []
        for domain in target_domains:
            domain_results = search(f"domain:{domain}", limit=50)
            for r in domain_results:
                if r["arxiv_id"] != arxiv_id:
                    candidates.append({
                        "id": r["arxiv_id"],
                        "text": r.get("wiki_content", r.get("title", "")),
                        "domain": domain,
                        "title": r.get("title", ""),
                    })

        if not candidates:
            return {"connections": [], "source": arxiv_id}

        # Find semantic similarities
        connections = await self.embed_client.find_cross_domain_connections(
            source_text, candidates, top_k=top_k
        )

        # Enrich results
        for conn in connections:
            paper = get_paper_by_id(conn["id"])
            if paper:
                conn["title"] = paper.get("title", "")
                conn["abstract"] = paper.get("abstract", "")[:200]

        return {
            "source": arxiv_id,
            "source_domain": source_domain,
            "connections": connections,
        }


# Singleton instances
embed_client = EmbeddingClient()
embed_store = EmbeddingStore()
hybrid_engine = HybridSearchEngine()

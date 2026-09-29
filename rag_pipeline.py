"""
Advanced RAG Pipeline Engine for Enterprise Icinga Observability
Implements and benchmarks three architectures:
1. NaiveSemanticRetriever (Baseline Dense Vector Search)
2. HybridRRFRetriever (BM25 Lexical + Dense Vector + Reciprocal Rank Fusion)
3. HyperOptimizedSemanticRetriever (Semantic Chunking + Multi-Query + HyDE + Cross-Encoder Reranker + Threshold Filter)
"""

import os
import re
import time
import math
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from rag_chunkers import BaseChunker, Chunk, DomainSemanticChunker, FixedTokenChunker, RecursiveCharChunker

# Suppress TF/huggingface parallelism warnings
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


# =============================================================================
# 1. EMBEDDING & CROSS-ENCODER MODEL MANAGERS
# =============================================================================

class EmbeddingManager:
    """Manages dense vector embeddings with device acceleration and caching."""
    _instance = None

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: Optional[str] = None):
        import torch
        from sentence_transformers import SentenceTransformer

        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.model_name = model_name
        self.model = SentenceTransformer(model_name, device=self.device)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

    @classmethod
    def get_instance(cls, model_name: str = "all-MiniLM-L6-v2") -> "EmbeddingManager":
        if cls._instance is None:
            cls._instance = cls(model_name=model_name)
        return cls._instance

    def encode(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        if not texts:
            return np.empty((0, self.embedding_dim), dtype=np.float32)
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=normalize,
            show_progress_bar=False,
            batch_size=32
        )
        return embeddings


class CrossEncoderManager:
    """Manages Cross-Encoder for high-precision Joint Attention Re-Ranking."""
    _instance = None

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", device: Optional[str] = None):
        import torch
        from sentence_transformers import CrossEncoder

        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.model_name = model_name
        self.model = CrossEncoder(model_name, device=self.device)

    @classmethod
    def get_instance(cls, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> "CrossEncoderManager":
        if cls._instance is None:
            cls._instance = cls(model_name=model_name)
        return cls._instance

    def predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        if not pairs:
            return []
        scores = self.model.predict(pairs, show_progress_bar=False, batch_size=32)
        return scores.tolist() if hasattr(scores, "tolist") else list(scores)


# =============================================================================
# 2. LEXICAL BM25 SEARCH (for Hybrid baseline)
# =============================================================================

class BM25Engine:
    """Okapi BM25 index over text chunks."""
    def __init__(self, chunks: List[Chunk], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunks = chunks
        self.corpus_size = len(chunks)
        self.doc_len = []
        self.avg_doc_len = 0.0
        self.doc_freqs = {}
        self.idf = {}
        self.tokenized_corpus = []
        self._build_index()

    @staticmethod
    def tokenize(text: str) -> List[str]:
        clean_text = text.lower()
        tokens = re.findall(r'[a-z0-9_\-\./]+', clean_text)
        return [t for t in tokens if len(t) > 1]

    def _build_index(self):
        if not self.chunks:
            return

        total_len = 0
        for chunk in self.chunks:
            tokens = self.tokenize(chunk.text)
            self.tokenized_corpus.append(tokens)
            l = len(tokens)
            self.doc_len.append(l)
            total_len += l

            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        self.avg_doc_len = total_len / max(1, self.corpus_size)

        for token, df in self.doc_freqs.items():
            self.idf[token] = math.log(1.0 + (self.corpus_size - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Chunk, float]]:
        if not self.chunks or self.corpus_size == 0:
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        scores = [0.0] * self.corpus_size

        for token in query_tokens:
            if token not in self.idf:
                continue
            idf_val = self.idf[token]

            for idx, tokens in enumerate(self.tokenized_corpus):
                term_count = tokens.count(token)
                if term_count == 0:
                    continue
                doc_l = self.doc_len[idx]
                numerator = term_count * (self.k1 + 1.0)
                denominator = term_count + self.k1 * (1.0 - self.b + self.b * (doc_l / self.avg_doc_len))
                scores[idx] += idf_val * (numerator / denominator)

        ranked = []
        for idx, score in enumerate(scores):
            if score > 0:
                ranked.append((self.chunks[idx], float(score)))

        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


# =============================================================================
# 3. BASELINE RETRIEVER: NAIVE SEMANTIC RAG (Fixed Chunking + Bi-Encoder Dense)
# =============================================================================

class NaiveSemanticRetriever:
    """
    Baseline Naive Semantic RAG.
    - Uses Fixed-Token Chunker (256 tokens).
    - Bi-Encoder vector embedding cosine similarity.
    - No multi-query, no HyDE, no reranker.
    """
    def __init__(self, raw_documents: List[Dict[str, Any]], embedding_model_name: str = "all-MiniLM-L6-v2"):
        self.chunker = FixedTokenChunker(chunk_size_tokens=256, overlap_tokens=40)
        self.chunks = self.chunker.chunk_documents(raw_documents)
        self.embed_mgr = EmbeddingManager.get_instance(embedding_model_name)
        
        # Precompute embeddings
        texts = [c.text for c in self.chunks]
        self.embeddings = self.embed_mgr.encode(texts, normalize=True)

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        t0 = time.perf_counter()
        if not query.strip() or len(self.chunks) == 0:
            return []

        q_vec = self.embed_mgr.encode([query], normalize=True)
        scores = np.dot(self.embeddings, q_vec.T).squeeze()
        
        if scores.ndim == 0:
            scores = np.array([float(scores)])

        top_indices = np.argsort(scores)[::-1][:top_k]
        latency_ms = (time.perf_counter() - t0) * 1000.0

        results = []
        for rank, idx in enumerate(top_indices):
            chunk = self.chunks[idx]
            score = float(scores[idx])
            results.append({
                "chunk_id": chunk.id,
                "title": chunk.metadata.get("title", "Runbook"),
                "text": chunk.text,
                "score": score,
                "rank": rank + 1,
                "service_type": chunk.metadata.get("service_type", "general"),
                "strategy": "naive_semantic",
                "latency_ms": latency_ms
            })
        return results


# =============================================================================
# 4. STANDARD HYBRID RETRIEVER (BM25 + Dense + Reciprocal Rank Fusion)
# =============================================================================

class HybridRRFRetriever:
    """
    Standard Hybrid RAG.
    - Uses Recursive Character Chunker (800 chars).
    - BM25 Lexical Search + Bi-Encoder Dense Search.
    - Reciprocal Rank Fusion (RRF: score = 1 / (60 + rank)).
    """
    def __init__(self, raw_documents: List[Dict[str, Any]], embedding_model_name: str = "all-MiniLM-L6-v2"):
        self.chunker = RecursiveCharChunker(chunk_size=800, chunk_overlap=150)
        self.chunks = self.chunker.chunk_documents(raw_documents)
        self.embed_mgr = EmbeddingManager.get_instance(embedding_model_name)
        self.bm25 = BM25Engine(self.chunks)

        texts = [c.text for c in self.chunks]
        self.embeddings = self.embed_mgr.encode(texts, normalize=True)

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        t0 = time.perf_counter()
        if not query.strip() or len(self.chunks) == 0:
            return []

        # 1. BM25 Search
        bm25_hits = self.bm25.search(query, top_k=top_k * 4)

        # 2. Dense Vector Search
        q_vec = self.embed_mgr.encode([query], normalize=True)
        scores = np.dot(self.embeddings, q_vec.T).squeeze()
        if scores.ndim == 0:
            scores = np.array([float(scores)])
        dense_top_indices = np.argsort(scores)[::-1][:top_k * 4]

        # 3. Reciprocal Rank Fusion (RRF)
        RRF_K = 60
        rrf_scores = {}
        chunk_map = {}

        for rank, (chunk, bm25_score) in enumerate(bm25_hits):
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (RRF_K + (rank + 1)))

        for rank, idx in enumerate(dense_top_indices):
            chunk = self.chunks[idx]
            chunk_map[chunk.id] = chunk
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (RRF_K + (rank + 1)))

        sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)[:top_k]
        latency_ms = (time.perf_counter() - t0) * 1000.0

        results = []
        for rank, cid in enumerate(sorted_ids):
            chunk = chunk_map[cid]
            results.append({
                "chunk_id": chunk.id,
                "title": chunk.metadata.get("title", "Runbook"),
                "text": chunk.text,
                "score": rrf_scores[cid],
                "rank": rank + 1,
                "service_type": chunk.metadata.get("service_type", "general"),
                "strategy": "hybrid_rrf",
                "latency_ms": latency_ms
            })
        return results


# =============================================================================
# 5. HYPER-OPTIMIZED SEMANTIC RETRIEVER (Pillar 1 Technical Masterpiece)
# =============================================================================

class HyperOptimizedSemanticRetriever:
    """
    Hyper-Optimized Semantic RAG Engine.
    Key Architectural Levers:
    1. Domain-Aware Semantic Structural Chunking (Parent-Child Lineage).
    2. Multi-Query Expansion & Technical Synonym Injection.
    3. HyDE (Hypothetical Document Embeddings for AIOps RCA).
    4. Domain Metadata Pre-Filtering (Service & Severity Alignment).
    5. Joint Attention Cross-Encoder Re-Ranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`).
    6. Dynamic Relevance Thresholding (Filters out irrelevant noise / prevents hallucinations).
    7. Parent-Document Context Assembly.
    """
    DOMAIN_EXPANSIONS = {
        "mysql": ["mysql database error", "mariadb threads connected deadlock", "slow query log execution latency"],
        "disk": ["filesystem storage full df -h", "inode exhaustion /var/log unlinked open file", "disk space critical exit code 2"],
        "cpu": ["high cpu load average", "runaway worker thread wa% iowait", "check_load threshold breached"],
        "memory": ["oom killer out of memory", "check_mem memory usage high swap", "linux kernel process exit code 137"],
        "network": ["host down check_ping packet loss", "socket timeout icmp traceroute dns failure", "port 5665 unreachable"],
        "http": ["502 bad gateway upstream crashed", "504 gateway timeout proxy_read_timeout", "nginx php-fpm connection refused"],
        "ssl": ["ssl tls certificate expiration", "certbot renew check_ssl_cert x509", "tls handshake failure"],
        "elastic": ["opensearch elasticsearch cluster status red", "unassigned shards flood stage disk watermark", "index read_only_allow_delete"],
        "docker": ["docker container crashed exit code 137", "container restart crashloopbackoff", "docker daemon container failure"],
        "k8s": ["kubernetes pod crashloopbackoff", "kubectl describe pod oomkilled 137", "liveness probe failed"],
        "redis": ["redis used_memory maxmemory oom", "redis-cli evicted_keys_per_sec allkeys-lru", "cache eviction storm"],
        "rabbitmq": ["rabbitmq queue congestion unacknowledged messages", "rabbitmqctl check_alarms vm_memory_high_watermark", "consumer starvation dlx"],
        "dns": ["dns resolution failed nxdomain servfail", "systemd-resolved coredns ndots resolv.conf", "nameserver udp 53 timeout"],
        "icinga": ["icinga director config validation failed exit code 1", "icinga2 daemon -C syntax error", "business process bpm tree redundancy quorum loss"]
    }

    def __init__(
        self,
        raw_documents: List[Dict[str, Any]],
        embedding_model_name: str = "all-MiniLM-L6-v2",
        reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        relevance_threshold: float = 0.05  # Calibrated Sigmoid threshold
    ):
        self.chunker = DomainSemanticChunker()
        self.chunks = self.chunker.chunk_documents(raw_documents)
        self.embed_mgr = EmbeddingManager.get_instance(embedding_model_name)
        self.reranker_mgr = CrossEncoderManager.get_instance(reranker_model_name)
        self.relevance_threshold = relevance_threshold

        # Separate child chunks (for vector search) and parent chunks (for context retrieval)
        self.child_chunks = [c for c in self.chunks if not c.metadata.get("is_parent")]
        self.parent_map = {c.id: c for c in self.chunks if c.metadata.get("is_parent")}

        # Precompute dense embeddings for all child chunks
        texts = [c.text for c in self.child_chunks]
        self.embeddings = self.embed_mgr.encode(texts, normalize=True)

    def _expand_query(self, query: str) -> List[str]:
        """Multi-Query Expansion & HyDE Synthetic Hypothesis Generation."""
        expanded_queries = [query]
        q_lower = query.lower()

        # Multi-Query Expansion via Domain Synonym Map
        for s_type, expansions in self.DOMAIN_EXPANSIONS.items():
            if s_type in q_lower or any(kw in q_lower for kw in expansions[0].split()):
                expanded_queries.extend(expansions[:2])

        # HyDE: Generate synthetic diagnostic hypothesis snippet
        hyde_hypo = f"Diagnostic Commands and Root Cause Analysis for incident: {query}."
        expanded_queries.append(hyde_hypo)

        return list(dict.fromkeys(expanded_queries))[:4]

    def _extract_query_service_type(self, query: str) -> Optional[str]:
        """Identifies domain service for soft metadata filtering."""
        q_lower = query.lower()
        for s_type, kws in DomainSemanticChunker.SERVICE_KEYWORDS.items():
            for kw in kws:
                if kw in q_lower:
                    return s_type
        return None

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        candidate_pool_size: int = 15,
        return_parent_context: bool = True
    ) -> List[Dict[str, Any]]:
        t0 = time.perf_counter()
        if not query.strip() or len(self.child_chunks) == 0:
            return []

        # 1. Multi-Query Expansion & HyDE
        queries = self._expand_query(query)
        target_service = self._extract_query_service_type(query)

        # 2. Broad Dense Candidate Retrieval across expanded queries
        q_vecs = self.embed_mgr.encode(queries, normalize=True)
        sim_matrices = np.dot(self.embeddings, q_vecs.T)  # (N_chunks, N_queries)
        max_sim_scores = np.max(sim_matrices, axis=1)

        # Apply soft domain boost for matching metadata
        if target_service:
            for idx, chunk in enumerate(self.child_chunks):
                if chunk.metadata.get("service_type") == target_service:
                    max_sim_scores[idx] += 0.08

        # Select Top-M candidate pool for Cross-Encoder
        candidate_indices = np.argsort(max_sim_scores)[::-1][:candidate_pool_size]
        candidates = [self.child_chunks[idx] for idx in candidate_indices]

        # 3. Cross-Encoder Joint-Attention Re-Ranking
        pairs = [(query, c.text) for c in candidates]
        rerank_scores = self.reranker_mgr.predict(pairs)

        # 4. Sort and apply Dynamic Relevance Thresholding (Sigmoid normalization)
        ranked_candidates = []
        for idx, raw_score in enumerate(rerank_scores):
            chunk = candidates[idx]
            # Convert logit to probability via Sigmoid
            prob_score = 1.0 / (1.0 + math.exp(-raw_score))
            
            if prob_score >= self.relevance_threshold:
                ranked_candidates.append((chunk, prob_score))

        # Sort descending by re-ranker score
        ranked_candidates.sort(key=lambda x: x[1], reverse=True)

        # 5. Assemble Hierarchical Parent Context (deduplicating parents)
        results = []
        seen_parents = set()
        latency_ms = (time.perf_counter() - t0) * 1000.0

        for chunk, score in ranked_candidates:
            parent_id = chunk.metadata.get("parent_id")
            if return_parent_context and parent_id and parent_id in self.parent_map:
                if parent_id in seen_parents:
                    continue
                seen_parents.add(parent_id)
                parent_chunk = self.parent_map[parent_id]
                ret_text = parent_chunk.text
                ret_title = parent_chunk.metadata.get("title", chunk.metadata.get("title"))
            else:
                if chunk.id in seen_parents:
                    continue
                seen_parents.add(chunk.id)
                ret_text = chunk.text
                ret_title = chunk.metadata.get("title", "Runbook")

            results.append({
                "chunk_id": chunk.id,
                "title": ret_title,
                "text": ret_text,
                "score": float(score),
                "rank": len(results) + 1,
                "service_type": chunk.metadata.get("service_type", "general"),
                "strategy": "hyper_optimized_semantic",
                "latency_ms": latency_ms
            })

            if len(results) >= top_k:
                break

        return results


# =============================================================================
# UNIFIED RAG RUNNER / FACTORY
# =============================================================================

def load_knowledge_base_documents() -> List[Dict[str, Any]]:
    """Loads all runbook and sample docs from the docs directory."""
    from knowledge_base import load_runbook_sections
    return load_runbook_sections()


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("Loading Knowledge Base documents...")
    docs = load_knowledge_base_documents()
    print(f"Loaded {len(docs)} document sections.")

    print("\nInitializing RAG Pipelines...")
    naive_rag = NaiveSemanticRetriever(docs)
    hybrid_rag = HybridRRFRetriever(docs)
    hyper_rag = HyperOptimizedSemanticRetriever(docs)

    test_queries = [
        "check_disk /var/log exit code 2 98% full",
        "502 Bad Gateway nginx upstream server crashed",
        "MySQL Too many connections and deadlock in IDO",
        "Kubernetes pod payment-service in CrashLoopBackOff OOMKilled",
        "Random completely unrelated weather question about rain"
    ]

    print("\n" + "=" * 80)
    print("DEMONSTRATION: RETRIEVAL HEAD-TO-HEAD COMPARISON")
    print("=" * 80)

    for q in test_queries:
        print(f"\n\U0001F50D QUERY: '{q}'")
        print("-" * 60)
        
        n_res = naive_rag.retrieve(q, top_k=1)
        h_res = hybrid_rag.retrieve(q, top_k=1)
        o_res = hyper_rag.retrieve(q, top_k=1)

        print(f"1. Naive Semantic:    Score={n_res[0]['score']:.4f} | Latency={n_res[0]['latency_ms']:.1f}ms | Title: {n_res[0]['title'][:55]}")
        print(f"2. Hybrid RRF:        Score={h_res[0]['score']:.4f} | Latency={h_res[0]['latency_ms']:.1f}ms | Title: {h_res[0]['title'][:55]}")
        if o_res:
            print(f"3. Hyper-Optimized:   Score={o_res[0]['score']:.4f} | Latency={o_res[0]['latency_ms']:.1f}ms | Title: {o_res[0]['title'][:55]}")
        else:
            print(f"3. Hyper-Optimized:   NOISE REJECTED (Threshold prevented hallucination!) \u2705")

import os
import re
import math
import threading
from typing import List, Dict, Any, Optional

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

VECTOR_STORE_DIR = "./chroma_db"
RUNBOOKS_FILE = "docs/troubleshooting_runbooks.md"
SAMPLE_DOCS_FILE = "docs/sample_troubleshooting.md"

_documents: List[Dict[str, Any]] = []
_bm25_index: Optional["BM25Ranker"] = None
_vectorstore = None
_vector_init_lock = threading.Lock()
_vector_initialized = False


# =============================================================================
# BM25 LEXICAL SEARCH (Instant 0ms, Zero-Dep, Precision for DevOps/AIOps)
# =============================================================================

class BM25Ranker:
    """
    High-performance Okapi BM25 ranker for exact IT keywords, error codes,
    command names, file paths, and exit codes.
    """
    def __init__(self, documents: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents = documents
        self.doc_len = []
        self.avg_doc_len = 0.0
        self.doc_freqs = {}
        self.idf = {}
        self.corpus_size = len(documents)
        self.tokenized_corpus = []
        self._build_index()

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenize text preserving error codes, file paths, and alphanumeric tokens."""
        clean_text = text.lower()
        # Extract word tokens, paths, exit codes, commands
        tokens = re.findall(r'[a-z0-9_\-\./]+', clean_text)
        return [t for t in tokens if len(t) > 1]

    def _build_index(self):
        if not self.documents:
            return

        total_len = 0
        for doc in self.documents:
            # Combine title and content with 2x weight for title
            full_text = f"{doc.get('title', '')} {doc.get('title', '')} {doc.get('content', '')}"
            tokens = self.tokenize(full_text)
            self.tokenized_corpus.append(tokens)
            doc_len = len(tokens)
            self.doc_len.append(doc_len)
            total_len += doc_len

            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        self.avg_doc_len = total_len / max(1, self.corpus_size)

        for token, df in self.doc_freqs.items():
            self.idf[token] = math.log(1.0 + (self.corpus_size - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.documents or self.corpus_size == 0:
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        scores = [0.0] * self.corpus_size

        for token in query_tokens:
            if token not in self.idf:
                continue
            idf_val = self.idf[token]

            for doc_idx, tokens in enumerate(self.tokenized_corpus):
                term_count = tokens.count(token)
                if term_count == 0:
                    continue
                
                doc_l = self.doc_len[doc_idx]
                numerator = term_count * (self.k1 + 1.0)
                denominator = term_count + self.k1 * (1.0 - self.b + self.b * (doc_l / self.avg_doc_len))
                scores[doc_idx] += idf_val * (numerator / denominator)

        ranked = []
        for idx, score in enumerate(scores):
            if score > 0:
                ranked.append({
                    "doc": self.documents[idx],
                    "score": score,
                    "index": idx
                })

        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]


# =============================================================================
# DOCUMENT INGESTION
# =============================================================================

def load_runbook_sections() -> List[Dict[str, Any]]:
    """Loads all runbook markdown files and splits into structured sections."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    files_to_load = [
        os.path.join(base_dir, RUNBOOKS_FILE),
        os.path.join(base_dir, SAMPLE_DOCS_FILE)
    ]

    sections = []

    for file_path in files_to_load:
        if not os.path.exists(file_path):
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            parts = re.split(r'\n(?=##\s+)', content)
            for part in parts:
                part = part.strip()
                if not part or part.startswith("# Enterprise AIOps") or part.startswith("# Icinga 2 Troubleshooting"):
                    continue

                lines = part.split("\n")
                title_line = lines[0].replace("##", "").strip() if lines else "General Runbook"
                
                sections.append({
                    "title": title_line,
                    "content": part,
                    "source": os.path.basename(file_path)
                })
        except Exception as e:
            print(f"Error loading {file_path}: {e}")

    return sections


def _init_documents():
    global _documents, _bm25_index
    if not _documents:
        _documents = load_runbook_sections()
        if _documents:
            _bm25_index = BM25Ranker(_documents)


def _init_vectorstore_background():
    """Initializes ChromaDB in a separate thread so it doesn't block queries."""
    global _vectorstore, _vector_initialized
    with _vector_init_lock:
        if _vector_initialized:
            return
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_community.vectorstores import Chroma
            from langchain_core.documents import Document

            _init_documents()
            if not _documents:
                return

            emb = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"}
            )
            langchain_docs = [
                Document(page_content=doc["content"], metadata={"title": doc["title"], "source": doc["source"]})
                for doc in _documents
            ]
            _vectorstore = Chroma.from_documents(
                documents=langchain_docs,
                embedding=emb,
                persist_directory=VECTOR_STORE_DIR
            )
            _vector_initialized = True
        except Exception as e:
            _vector_initialized = True


# Initialize documents & BM25 immediately (sub-millisecond)
_init_documents()


_hyper_retriever = None
_hyper_init_lock = threading.Lock()


def _get_hyper_retriever() -> Optional[Any]:
    global _hyper_retriever
    if _hyper_retriever is not None:
        return _hyper_retriever
    with _hyper_init_lock:
        if _hyper_retriever is None:
            try:
                from rag_pipeline import HyperOptimizedSemanticRetriever
                _init_documents()
                if _documents:
                    _hyper_retriever = HyperOptimizedSemanticRetriever(_documents)
            except Exception as e:
                pass
    return _hyper_retriever


# =============================================================================
# HYPER-OPTIMIZED SEMANTIC RAG SEARCH (with instant BM25 fallback)
# =============================================================================

def search_troubleshooting_guides(query: str, top_k: int = 2) -> str:
    """
    Hyper-Optimized Semantic RAG Search combining Domain-Aware Structural Chunking,
    Multi-Query Expansion, HyDE, and Cross-Encoder Re-Ranking.
    Gracefully falls back to BM25 lexical ranker if embedding pipeline is initializing.
    """
    if not query or not query.strip():
        return "No query provided for runbook search."

    _init_documents()
    if not _documents:
        return "No knowledge base documents available."

    clean_query = query.strip()

    # 1. Try Hyper-Optimized Semantic RAG (Cross-Encoder + Parent Lineage)
    try:
        retriever = _get_hyper_retriever()
        if retriever is not None:
            hits = retriever.retrieve(clean_query, top_k=top_k)
            if hits:
                results = [f"📖 **{h['title']}**\n{h['text']}" for h in hits]
                return "\n\n---\n\n".join(results)
    except Exception:
        pass

    # 2. Fallback to BM25 Lexical Search (Instant, zero-dep)
    if _bm25_index:
        bm25_results = _bm25_index.search(clean_query, top_k=top_k)
        if bm25_results:
            results = [f"📖 **{item['doc']['title']}**\n{item['doc']['content']}" for item in bm25_results]
            return "\n\n---\n\n".join(results)

    # 3. Fallback: Return top general document
    return f"📖 **{_documents[0]['title']}**\n{_documents[0]['content']}"



if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("Testing Instant BM25 + Hybrid RAG Pipeline...")
    
    test_queries = [
        "check_disk exit code 2 98% full",
        "502 Bad Gateway nginx upstream",
        "How do I diagnose a host down alert?",
        "MySQL Too many connections deadlock",
        "check_mem memory usage 97% OOM killer",
        "Elasticsearch status red unassigned shards"
    ]
    
    for q in test_queries:
        print(f"\n==========================================")
        print(f"QUERY: '{q}'")
        print(f"==========================================")
        res = search_troubleshooting_guides(q, top_k=1)
        print(res[:250] + "...\n")

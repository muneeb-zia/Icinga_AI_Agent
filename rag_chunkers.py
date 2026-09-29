"""
RAG Chunking Engine for Enterprise AIOps & Icinga Observability
Implements and benchmarks:
1. FixedTokenChunker (Fixed window with sliding overlap)
2. RecursiveCharChunker (Hierarchical separator splitting)
3. DomainSemanticChunker (Icinga/AIOps domain-aware structural chunker with parent-child lineage)
"""

import re
import os
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class Chunk:
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tokens_estimate: int = 0

    def __post_init__(self):
        if not self.tokens_estimate:
            # Approximate 1 token ~ 4 characters (standard heuristics)
            self.tokens_estimate = max(1, len(self.text) // 4)


class BaseChunker:
    """Abstract Base Class for document chunkers."""
    def chunk_document(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        raise NotImplementedError

    def chunk_documents(self, docs: List[Dict[str, Any]]) -> List[Chunk]:
        all_chunks = []
        for idx, doc in enumerate(docs):
            text = doc.get("content", "")
            meta = {k: v for k, v in doc.items() if k != "content"}
            meta["doc_index"] = idx
            all_chunks.extend(self.chunk_document(text, meta))
        return all_chunks


# =============================================================================
# 1. FIXED TOKEN / WORD CHUNKER
# =============================================================================

class FixedTokenChunker(BaseChunker):
    """
    Splits text into fixed token windows with a sliding overlap.
    Simulates naive RAG chunking commonly used in baseline vector DB setups.
    """
    def __init__(self, chunk_size_tokens: int = 256, overlap_tokens: int = 40):
        self.chunk_size_tokens = chunk_size_tokens
        self.overlap_tokens = overlap_tokens
        self.words_per_token = 0.75  # ~1 token per 0.75 words

    def chunk_document(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        meta = metadata or {}
        words = text.split()
        if not words:
            return []

        words_per_chunk = int(self.chunk_size_tokens * self.words_per_token)
        overlap_words = int(self.overlap_tokens * self.words_per_token)
        step = max(1, words_per_chunk - overlap_words)

        chunks = []
        doc_idx = meta.get("doc_index", 0)
        source = meta.get("source", "doc")
        
        for idx, i in enumerate(range(0, len(words), step)):
            chunk_words = words[i:i + words_per_chunk]
            if not chunk_words:
                break
            chunk_text = " ".join(chunk_words)
            chunk_id = f"fixed_{source}_{doc_idx}_{idx}"
            
            chunk_meta = dict(meta)
            chunk_meta.update({
                "chunk_id": chunk_id,
                "chunk_index": idx,
                "strategy": "fixed_token",
                "chunk_size_tokens": self.chunk_size_tokens
            })
            
            chunks.append(Chunk(
                id=chunk_id,
                text=chunk_text,
                metadata=chunk_meta,
                tokens_estimate=len(chunk_words) // 3 * 4
            ))
            if i + words_per_chunk >= len(words):
                break

        return chunks


# =============================================================================
# 2. RECURSIVE CHARACTER CHUNKER
# =============================================================================

class RecursiveCharChunker(BaseChunker):
    """
    Recursively splits text by a prioritized list of separators
    (e.g., Markdown headers, double newlines, single newlines, sentences).
    """
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150, separators: Optional[List[str]] = None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n## ", "\n### ", "\n\n", "\n", ". ", " "]

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        if not separators:
            return [text] if text else []
        
        separator = separators[0]
        splits = []
        if separator in text:
            parts = text.split(separator)
            for i, part in enumerate(parts):
                if not part:
                    continue
                # Re-attach header indicator if needed
                if separator.startswith("\n#") and i > 0:
                    part = separator.strip() + " " + part
                splits.append(part)
        else:
            splits = [text]

        result = []
        for s in splits:
            if len(s) <= self.chunk_size:
                result.append(s)
            elif len(separators) > 1:
                result.extend(self._split_text(s, separators[1:]))
            else:
                # Force slice if no more separators
                for j in range(0, len(s), self.chunk_size - self.chunk_overlap):
                    result.append(s[j:j + self.chunk_size])

        # Merge tiny chunks with overlap
        merged = []
        curr = ""
        for item in result:
            if not curr:
                curr = item
            elif len(curr) + len(item) + 1 <= self.chunk_size:
                curr += "\n" + item
            else:
                merged.append(curr)
                overlap_text = curr[-self.chunk_overlap:] if len(curr) > self.chunk_overlap else ""
                curr = overlap_text + "\n" + item if overlap_text else item
        if curr:
            merged.append(curr)

        return merged

    def chunk_document(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        meta = metadata or {}
        raw_chunks = self._split_text(text, self.separators)
        doc_idx = meta.get("doc_index", 0)
        source = meta.get("source", "doc")
        
        chunks = []
        for idx, c_text in enumerate(raw_chunks):
            chunk_id = f"rec_{source}_{doc_idx}_{idx}"
            chunk_meta = dict(meta)
            chunk_meta.update({
                "chunk_id": chunk_id,
                "chunk_index": idx,
                "strategy": "recursive_char"
            })
            chunks.append(Chunk(
                id=chunk_id,
                text=c_text.strip(),
                metadata=chunk_meta,
                tokens_estimate=len(c_text) // 4
            ))
        return chunks


# =============================================================================
# 3. DOMAIN-AWARE SEMANTIC STRUCTURAL CHUNKER (Hyper-Optimized for AIOps)
# =============================================================================

class DomainSemanticChunker(BaseChunker):
    """
    Enterprise AIOps & Icinga Domain-Aware Chunker.
    Key Innovations:
    1. Preserves Semantic Integrity: Separates alert sections by Title, Diagnostic Commands,
       Root Cause Analysis (RCA), and Remediation Plan.
    2. Enriches Metadata: Extracts service type, severity, error codes, and tool actions.
    3. Hierarchical Context (Parent-Child Indexing):
       - Child Chunks: Sub-sections (Diagnostic / RCA / Remediation) for high-precision vector search.
       - Parent Document: Stores the full holistic runbook to prevent context truncation.
    """
    SERVICE_KEYWORDS = {
        "mysql": ["mysql", "mariadb", "innodb", "sql", "threads_connected", "slow_log", "deadlock"],
        "disk": ["disk", "filesystem", "inode", "df -h", "du -sh", "storage", "/var/log", "unlinked"],
        "cpu": ["cpu", "load average", "runaway", "check_load", "wa%", "iowait", "top", "htop"],
        "memory": ["memory", "ram", "swap", "oom", "oomkiller", "exit code 137", "free -m", "check_mem"],
        "network": ["network", "ping", "host down", "packet loss", "unreachable", "traceroute", "5665"],
        "http": ["http", "nginx", "apache", "502", "504", "bad gateway", "timeout", "proxy", "php-fpm", "check_http"],
        "ssl": ["ssl", "tls", "certificate", "certbot", "check_ssl_cert", "x509", "expired"],
        "elastic": ["elasticsearch", "opensearch", "unassigned shards", "cluster red", "cluster yellow", "shards"],
        "docker": ["docker", "container", "crashloopbackoff", "docker-compose", "docker ps", "check_docker"],
        "k8s": ["kubernetes", "k8s", "pod", "crashloopbackoff", "kubectl", "oomkilled", "liveness probe", "check_k8s"],
        "redis": ["redis", "redis-cli", "cache", "eviction", "allkeys-lru", "maxmemory", "check_redis"],
        "rabbitmq": ["rabbitmq", "queue", "rabbitmqctl", "unacknowledged", "dead letter", "dlx", "check_rabbitmq"],
        "dns": ["dns", "coredns", "resolv.conf", "dig", "systemd-resolved", "ndots", "nxdomain", "check_dns"],
        "icinga": ["icinga", "director", "satellite", "zone", "icinga2 daemon -C", "bpm", "business process", "check_icinga"]
    }

    SEVERITY_KEYWORDS = {
        "CRITICAL": ["critical", "down", "fatal", "oom", "panic", "lock", "unreachable", "137", "502", "red"],
        "WARNING": ["warning", "degraded", "high", "spike", "saturation", "expiring", "yellow", "504"],
        "OK": ["ok", "recovered", "healthy", "green"]
    }

    def _extract_service_type(self, text: str) -> str:
        text_lower = text.lower()
        for s_type, kws in self.SERVICE_KEYWORDS.items():
            for kw in kws:
                if kw in text_lower:
                    return s_type
        return "general"

    def _extract_severity(self, text: str) -> str:
        text_upper = text.upper()
        for sev, kws in self.SEVERITY_KEYWORDS.items():
            for kw in kws:
                if kw in text_upper:
                    return sev
        return "UNKNOWN"

    def _extract_error_codes(self, text: str) -> List[str]:
        patterns = [
            r'\b[1-5][0-9]{2}\b',                     # HTTP codes (502, 504, 404, etc.)
            r'\bexit code \d+\b',                     # Exit codes (exit code 137, 2, 1)
            r'\b[A-Z_]{4,30}\b',                      # Error tokens like OOMKILLED, NXDOMAIN, SERVFAIL
        ]
        found = set()
        for pat in patterns:
            matches = re.findall(pat, text, re.IGNORECASE)
            for m in matches:
                m_str = m.strip().upper()
                if m_str not in {"ERROR", "ALERT", "CHECK", "PLAN", "NAME", "HOST", "ROOT", "CASE", "TRUE", "FALSE"}:
                    found.add(m_str)
        return sorted(list(found))[:6]

    def _chunk_single_section(self, section_text: str, meta: Dict[str, Any], parent_id: str, title: str) -> List[Chunk]:
        """Splits a single section into parent and child chunks."""
        chunks = []
        service_type = self._extract_service_type(section_text)
        severity = self._extract_severity(section_text)
        error_codes = self._extract_error_codes(section_text)

        # 1. Parent Chunk (Full Section)
        parent_meta = dict(meta)
        parent_meta.update({
            "title": title,
            "service_type": service_type,
            "severity": severity,
            "error_codes": error_codes,
            "is_parent": True,
            "chunk_id": parent_id,
            "strategy": "domain_semantic_parent"
        })
        parent_chunk = Chunk(
            id=parent_id,
            text=section_text,
            metadata=parent_meta,
            tokens_estimate=len(section_text) // 4
        )
        chunks.append(parent_chunk)

        # 2. Child Chunks (Subsections: Diagnostics, RCA, Remediation)
        subsections = re.split(r'\n(?=###\s+)', section_text)
        child_count = 0
        for sub_idx, sub in enumerate(subsections):
            sub = sub.strip()
            if not sub:
                continue

            sub_lines = sub.split("\n")
            if sub.startswith("### "):
                sub_title = sub_lines[0].replace("###", "").strip()
            elif sub.startswith("## "):
                sub_title = "Overview & Symptoms"
            else:
                sub_title = f"Topic_{sub_idx}"

            child_id = f"{parent_id}_child_{child_count}"
            child_count += 1
            child_text = f"**Section: {title} | Sub-Topic: {sub_title}**\n{sub}"

            child_meta = dict(meta)
            child_meta.update({
                "title": title,
                "sub_title": sub_title,
                "service_type": service_type,
                "severity": severity,
                "error_codes": error_codes,
                "is_parent": False,
                "parent_id": parent_id,
                "parent_text": section_text,
                "chunk_id": child_id,
                "strategy": "domain_semantic_child"
            })

            chunks.append(Chunk(
                id=child_id,
                text=child_text,
                metadata=child_meta,
                tokens_estimate=len(child_text) // 4
            ))

        return chunks

    def chunk_document(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        meta = metadata or {}
        doc_idx = meta.get("doc_index", 0)
        source = meta.get("source", "doc")
        
        # If the document is already a single section (e.g. from load_runbook_sections)
        if meta.get("title") and not re.search(r'\n##\s+', text):
            title = meta["title"]
            parent_id = f"parent_{source}_{doc_idx}_{hashlib.md5(title.encode()).hexdigest()[:6]}"
            return self._chunk_single_section(text, meta, parent_id, title)

        # Otherwise split by top-level section headers ("## <Title>")
        sections = re.split(r'\n(?=##\s+)', text)
        all_chunks = []
        for sec_idx, section in enumerate(sections):
            sec_text = section.strip()
            if not sec_text or sec_text.startswith("# Enterprise AIOps") or sec_text.startswith("# Icinga 2 Troubleshooting"):
                continue

            lines = sec_text.split("\n")
            title = lines[0].replace("##", "").strip() if lines else f"Section_{sec_idx}"
            parent_id = f"parent_{source}_{doc_idx}_{sec_idx}_{hashlib.md5(title.encode()).hexdigest()[:6]}"
            all_chunks.extend(self._chunk_single_section(sec_text, meta, parent_id, title))

        return all_chunks


# =============================================================================
# CHUNKER FACTORY
# =============================================================================

def get_chunker(strategy: str = "domain_semantic", **kwargs) -> BaseChunker:
    """Factory method to instantiate chunker strategy."""
    strat = strategy.lower().strip()
    if strat in {"fixed", "fixed_token", "fixed_window"}:
        return FixedTokenChunker(
            chunk_size_tokens=kwargs.get("chunk_size_tokens", 256),
            overlap_tokens=kwargs.get("overlap_tokens", 40)
        )
    elif strat in {"recursive", "recursive_char", "hierarchical"}:
        return RecursiveCharChunker(
            chunk_size=kwargs.get("chunk_size", 800),
            chunk_overlap=kwargs.get("chunk_overlap", 150)
        )
    elif strat in {"domain", "domain_semantic", "semantic", "hyper_optimized"}:
        return DomainSemanticChunker()
    else:
        raise ValueError(f"Unknown chunking strategy: {strategy}. Options: fixed, recursive, domain_semantic")

"""
Automated 50+ Query Empirical Benchmark Suite for Enterprise RAG Architectures
Compares:
1. Baseline Naive Semantic RAG (Fixed-Token 256 + Dense Vector)
2. Standard Hybrid RAG (Recursive-Char 800 + BM25 + Dense + RRF)
3. Hyper-Optimized Semantic RAG (Domain-Aware Chunking + Multi-Query + HyDE + Cross-Encoder + Threshold Filter)
"""

import os
import sys
import json
import time
import csv
from typing import List, Dict, Any, Tuple
import numpy as np

from rag_pipeline import (
    load_knowledge_base_documents,
    NaiveSemanticRetriever,
    HybridRRFRetriever,
    HyperOptimizedSemanticRetriever
)

# Set UTF-8 output encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# =============================================================================
# 50+ ENTERPRISE GOLDEN EVALUATION QUERY DATASET
# =============================================================================

BENCHMARK_DATASET: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # 1. NETWORK & HOST CONNECTIVITY (6 Queries)
    # -------------------------------------------------------------------------
    {
        "id": "Q01",
        "category": "Network & Host Connectivity",
        "query": "CRITICAL - 100% packet loss hostalive socket timeout",
        "expected_service": "network",
        "expected_keywords": ["Host Down", "Network Unreachability", "Ping Timeout"],
        "is_distractor": False
    },
    {
        "id": "Q02",
        "category": "Network & Host Connectivity",
        "query": "Why is the core gateway unreachable for multiple subnet nodes?",
        "expected_service": "network",
        "expected_keywords": ["Host Down", "Network Unreachability"],
        "is_distractor": False
    },
    {
        "id": "Q03",
        "category": "Network & Host Connectivity",
        "query": "Port 5665 connection refused when master polls satellite agent",
        "expected_service": "network",
        "expected_keywords": ["Host Down", "Network Unreachability", "Satellite Node Sync"],
        "is_distractor": False
    },
    {
        "id": "Q04",
        "category": "Network & Host Connectivity",
        "query": "DNS resolution failed NXDOMAIN with dig timeout",
        "expected_service": "dns",
        "expected_keywords": ["DNS Resolution Failures", "CoreDNS"],
        "is_distractor": False
    },
    {
        "id": "Q05",
        "category": "Network & Host Connectivity",
        "query": "High ndots in resolv.conf causing massive latency on external domain lookups",
        "expected_service": "dns",
        "expected_keywords": ["DNS Resolution Failures", "CoreDNS", "Resolv.conf"],
        "is_distractor": False
    },
    {
        "id": "Q06",
        "category": "Network & Host Connectivity",
        "query": "systemd-resolved local DNS cache deadlock hung listening socket",
        "expected_service": "dns",
        "expected_keywords": ["DNS Resolution Failures", "systemd-resolved"],
        "is_distractor": False
    },

    # -------------------------------------------------------------------------
    # 2. DISK & STORAGE SUBSYSTEMS (6 Queries)
    # -------------------------------------------------------------------------
    {
        "id": "Q07",
        "category": "Disk & Storage Subsystems",
        "query": "check_disk CRITICAL / is 98% full free 1.2 GB exit code 2",
        "expected_service": "disk",
        "expected_keywords": ["Disk Space Full", "Filesystem Read-Only", "Inode Depletion"],
        "is_distractor": False
    },
    {
        "id": "Q08",
        "category": "Disk & Storage Subsystems",
        "query": "df -i shows 100% inode usage in /var/spool/postfix but disk space has 40GB free",
        "expected_service": "disk",
        "expected_keywords": ["Disk Space Full", "Inode Depletion"],
        "is_distractor": False
    },
    {
        "id": "Q09",
        "category": "Disk & Storage Subsystems",
        "query": "Unlinked open log file deleted with rm still holding space in lsof +L1",
        "expected_service": "disk",
        "expected_keywords": ["Disk Space Full", "lsof +L1"],
        "is_distractor": False
    },
    {
        "id": "Q10",
        "category": "Disk & Storage Subsystems",
        "query": "journalctl vacuum systemd log bloat filling up /var/log partition",
        "expected_service": "disk",
        "expected_keywords": ["Disk Space Full", "Log Bloat"],
        "is_distractor": False
    },
    {
        "id": "Q11",
        "category": "Disk & Storage Subsystems",
        "query": "Docker build cache and dangling images filling root mount /var/lib/docker",
        "expected_service": "disk",
        "expected_keywords": ["Disk Space Full", "Docker"],
        "is_distractor": False
    },
    {
        "id": "Q12",
        "category": "Disk & Storage Subsystems",
        "query": "Filesystem mounted read-only after I/O error on root partition",
        "expected_service": "disk",
        "expected_keywords": ["Disk Space Full", "Filesystem Read-Only"],
        "is_distractor": False
    },

    # -------------------------------------------------------------------------
    # 3. CPU & MEMORY PERFORMANCE (6 Queries)
    # -------------------------------------------------------------------------
    {
        "id": "Q13",
        "category": "CPU & Memory Performance",
        "query": "check_load CRITICAL load average 28.5 24.1 19.8 high iowait",
        "expected_service": "cpu",
        "expected_keywords": ["High CPU Load", "Runaway Process"],
        "is_distractor": False
    },
    {
        "id": "Q14",
        "category": "CPU & Memory Performance",
        "query": "Uninterruptible sleep state D processes causing high load in top wa%",
        "expected_service": "cpu",
        "expected_keywords": ["High CPU Load", "Runaway Process"],
        "is_distractor": False
    },
    {
        "id": "Q15",
        "category": "CPU & Memory Performance",
        "query": "check_mem CRITICAL memory usage 97% OOM killer triggered",
        "expected_service": "memory",
        "expected_keywords": ["High Memory Usage", "OOM Killer"],
        "is_distractor": False
    },
    {
        "id": "Q16",
        "category": "CPU & Memory Performance",
        "query": "Process killed with signal 9 exit code 137 in dmesg kernel out of memory",
        "expected_service": "memory",
        "expected_keywords": ["High Memory Usage", "OOM Killer"],
        "is_distractor": False
    },
    {
        "id": "Q17",
        "category": "CPU & Memory Performance",
        "query": "How to drop linux filesystem page cache cleanly with sync echo 3",
        "expected_service": "memory",
        "expected_keywords": ["High Memory Usage", "drop_caches"],
        "is_distractor": False
    },
    {
        "id": "Q18",
        "category": "CPU & Memory Performance",
        "query": "Runaway worker thread spinning at 100% user CPU utilization kill -15",
        "expected_service": "cpu",
        "expected_keywords": ["High CPU Load", "Runaway Process"],
        "is_distractor": False
    },

    # -------------------------------------------------------------------------
    # 4. DATABASE & IN-MEMORY CACHE (7 Queries)
    # -------------------------------------------------------------------------
    {
        "id": "Q19",
        "category": "Database & Cache Systems",
        "query": "check_mysql CRITICAL Can't connect to MySQL server Too many connections",
        "expected_service": "mysql",
        "expected_keywords": ["MySQL", "IDO Database Degradation"],
        "is_distractor": False
    },
    {
        "id": "Q20",
        "category": "Database & Cache Systems",
        "query": "SHOW ENGINE INNODB STATUS shows deadlock on IDO history table queries",
        "expected_service": "mysql",
        "expected_keywords": ["MySQL", "IDO Database Degradation"],
        "is_distractor": False
    },
    {
        "id": "Q21",
        "category": "Database & Cache Systems",
        "query": "PURGE BINARY LOGS to free disk space on MariaDB volume",
        "expected_service": "mysql",
        "expected_keywords": ["MySQL", "IDO Database Degradation"],
        "is_distractor": False
    },
    {
        "id": "Q22",
        "category": "Database & Cache Systems",
        "query": "SET GLOBAL max_connections to resolve database pool exhaustion",
        "expected_service": "mysql",
        "expected_keywords": ["MySQL", "IDO Database Degradation"],
        "is_distractor": False
    },
    {
        "id": "Q23",
        "category": "Database & Cache Systems",
        "query": "check_redis CRITICAL used_memory greater than maxmemory eviction storm",
        "expected_service": "redis",
        "expected_keywords": ["Redis In-Memory Cache Saturation", "Eviction Storms"],
        "is_distractor": False
    },
    {
        "id": "Q24",
        "category": "Database & Cache Systems",
        "query": "Redis OOM command not allowed when maxmemory-policy is set to noeviction",
        "expected_service": "redis",
        "expected_keywords": ["Redis In-Memory Cache Saturation", "allkeys-lru"],
        "is_distractor": False
    },
    {
        "id": "Q25",
        "category": "Database & Cache Systems",
        "query": "Unversioned session cache keys without TTL filling Redis RAM",
        "expected_service": "redis",
        "expected_keywords": ["Redis In-Memory Cache Saturation"],
        "is_distractor": False
    },

    # -------------------------------------------------------------------------
    # 5. WEB SERVERS & REVERSE PROXIES (6 Queries)
    # -------------------------------------------------------------------------
    {
        "id": "Q26",
        "category": "Web Servers & Reverse Proxies",
        "query": "check_http CRITICAL HTTP/1.1 502 Bad Gateway nginx upstream crashed",
        "expected_service": "http",
        "expected_keywords": ["Web Server & Reverse Proxy Errors", "502", "Nginx"],
        "is_distractor": False
    },
    {
        "id": "Q27",
        "category": "Web Servers & Reverse Proxies",
        "query": "HTTP/1.1 504 Gateway Timeout upstream proxy_read_timeout exceeded",
        "expected_service": "http",
        "expected_keywords": ["Web Server & Reverse Proxy Errors", "504", "Nginx"],
        "is_distractor": False
    },
    {
        "id": "Q28",
        "category": "Web Servers & Reverse Proxies",
        "query": "Nginx connect() failed to php-fpm.sock permission denied",
        "expected_service": "http",
        "expected_keywords": ["Web Server & Reverse Proxy Errors", "Nginx"],
        "is_distractor": False
    },
    {
        "id": "Q29",
        "category": "Web Servers & Reverse Proxies",
        "query": "check_ssl_cert WARNING Certificate expires in 14 days certbot renewal",
        "expected_service": "ssl",
        "expected_keywords": ["SSL / TLS Certificate Expiry", "Certbot"],
        "is_distractor": False
    },
    {
        "id": "Q30",
        "category": "Web Servers & Reverse Proxies",
        "query": "How to force renew Let's Encrypt TLS certificate with certbot renew --force-renewal",
        "expected_service": "ssl",
        "expected_keywords": ["SSL / TLS Certificate Expiry", "Certbot"],
        "is_distractor": False
    },
    {
        "id": "Q31",
        "category": "Web Servers & Reverse Proxies",
        "query": "openssl s_client verification of x509 expiration dates on port 443",
        "expected_service": "ssl",
        "expected_keywords": ["SSL / TLS Certificate Expiry", "openssl"],
        "is_distractor": False
    },

    # -------------------------------------------------------------------------
    # 6. DISTRIBUTED SEARCH & MESSAGE QUEUES (6 Queries)
    # -------------------------------------------------------------------------
    {
        "id": "Q32",
        "category": "Search & Message Queues",
        "query": "Elasticsearch cluster health status red unassigned shards",
        "expected_service": "elastic",
        "expected_keywords": ["Elasticsearch / OpenSearch Red Cluster", "Unassigned Shards"],
        "is_distractor": False
    },
    {
        "id": "Q33",
        "category": "Search & Message Queues",
        "query": "OpenSearch disk flood-stage watermark 95% index.blocks.read_only_allow_delete",
        "expected_service": "elastic",
        "expected_keywords": ["Elasticsearch / OpenSearch Red Cluster", "flood-stage"],
        "is_distractor": False
    },
    {
        "id": "Q34",
        "category": "Search & Message Queues",
        "query": "How to reroute unassigned shards with retry_failed=true in OpenSearch",
        "expected_service": "elastic",
        "expected_keywords": ["Elasticsearch / OpenSearch Red Cluster", "reroute"],
        "is_distractor": False
    },
    {
        "id": "Q35",
        "category": "Search & Message Queues",
        "query": "check_rabbitmq CRITICAL order_processing queue depth 50000 unacknowledged messages",
        "expected_service": "rabbitmq",
        "expected_keywords": ["RabbitMQ Message Queue Congestion", "Unacknowledged"],
        "is_distractor": False
    },
    {
        "id": "Q36",
        "category": "Search & Message Queues",
        "query": "RabbitMQ vm_memory_high_watermark alarm triggered blocking publishers",
        "expected_service": "rabbitmq",
        "expected_keywords": ["RabbitMQ Message Queue Congestion", "alarm"],
        "is_distractor": False
    },
    {
        "id": "Q37",
        "category": "Search & Message Queues",
        "query": "Consumer starvation and dead-letter exchange DLX routing for poison pills",
        "expected_service": "rabbitmq",
        "expected_keywords": ["RabbitMQ Message Queue Congestion", "DLX"],
        "is_distractor": False
    },

    # -------------------------------------------------------------------------
    # 7. CONTAINERS & CLOUD NATIVE (6 Queries)
    # -------------------------------------------------------------------------
    {
        "id": "Q38",
        "category": "Containers & Cloud Native",
        "query": "check_docker CRITICAL container payment-api exited with status 137",
        "expected_service": "docker",
        "expected_keywords": ["Docker Container", "CrashLoopBackOff"],
        "is_distractor": False
    },
    {
        "id": "Q39",
        "category": "Containers & Cloud Native",
        "query": "Docker container port conflict address already in use bind failure",
        "expected_service": "docker",
        "expected_keywords": ["Docker Container", "CrashLoopBackOff"],
        "is_distractor": False
    },
    {
        "id": "Q40",
        "category": "Containers & Cloud Native",
        "query": "Kubernetes Pod in CrashLoopBackOff Terminated Reason OOMKilled",
        "expected_service": "k8s",
        "expected_keywords": ["Kubernetes Pod CrashLoopBackOff", "OOMKilled"],
        "is_distractor": False
    },
    {
        "id": "Q41",
        "category": "Containers & Cloud Native",
        "query": "kubectl logs --previous shows container crashed due to missing secret mount",
        "expected_service": "k8s",
        "expected_keywords": ["Kubernetes Pod CrashLoopBackOff", "OOMKilled"],
        "is_distractor": False
    },
    {
        "id": "Q42",
        "category": "Containers & Cloud Native",
        "query": "How to increase memory resources.limits in deployment yaml after pod OOMKilled",
        "expected_service": "k8s",
        "expected_keywords": ["Kubernetes Pod CrashLoopBackOff", "OOMKilled"],
        "is_distractor": False
    },
    {
        "id": "Q43",
        "category": "Containers & Cloud Native",
        "query": "Liveness probe failed HTTP 500 causing kubelet container restarts",
        "expected_service": "k8s",
        "expected_keywords": ["Kubernetes Pod CrashLoopBackOff", "OOMKilled"],
        "is_distractor": False
    },

    # -------------------------------------------------------------------------
    # 8. ICINGA 2 MONITORING CORE & BPM (7 Queries)
    # -------------------------------------------------------------------------
    {
        "id": "Q44",
        "category": "Icinga 2 Core & BPM Architecture",
        "query": "Icinga Director deployment failed Configuration validation failed exit code 1",
        "expected_service": "icinga",
        "expected_keywords": ["Icinga Director Config Deployment Validation", "Syntax Failure"],
        "is_distractor": False
    },
    {
        "id": "Q45",
        "category": "Icinga 2 Core & BPM Architecture",
        "query": "icinga2 daemon -C reports syntax error duplicate object definition",
        "expected_service": "icinga",
        "expected_keywords": ["Icinga Director Config Deployment Validation", "syntax error"],
        "is_distractor": False
    },
    {
        "id": "Q46",
        "category": "Icinga 2 Core & BPM Architecture",
        "query": "Business Process Module BPM node CRITICAL 1 of 3 database replicas available",
        "expected_service": "icinga",
        "expected_keywords": ["Business Process Module", "BPM Tree", "Service Hierarchy"],
        "is_distractor": False
    },
    {
        "id": "Q47",
        "category": "Icinga 2 Core & BPM Architecture",
        "query": "BPM redundancy quorum loss due to child service flap without scheduled downtime",
        "expected_service": "icinga",
        "expected_keywords": ["Business Process Module", "BPM Tree", "Service Hierarchy"],
        "is_distractor": False
    },
    {
        "id": "Q48",
        "category": "Icinga 2 Core & BPM Architecture",
        "query": "Icinga satellite zone endpoint not connected check latency greater than 15s",
        "expected_service": "icinga",
        "expected_keywords": ["Icinga 2 Satellite Node Sync", "Check Latency"],
        "is_distractor": False
    },
    {
        "id": "Q49",
        "category": "Icinga 2 Core & BPM Architecture",
        "query": "Satellite TLS certificate mismatch icinga2 pki verify against master ca.crt",
        "expected_service": "icinga",
        "expected_keywords": ["Icinga 2 Satellite Node Sync", "PKI"],
        "is_distractor": False
    },
    {
        "id": "Q50",
        "category": "Icinga 2 Core & BPM Architecture",
        "query": "Clock drift between master and satellite node causing check queue delays",
        "expected_service": "icinga",
        "expected_keywords": ["Icinga 2 Satellite Node Sync", "chronyc"],
        "is_distractor": False
    },

    # -------------------------------------------------------------------------
    # 9. NEGATIVE / DISTRACTOR / OUT-OF-DOMAIN QUERIES (5 Queries)
    # -------------------------------------------------------------------------
    {
        "id": "Q51",
        "category": "Distractors & Out-of-Domain",
        "query": "What is the weather forecast in Paris tomorrow with high precipitation?",
        "expected_service": "NONE",
        "expected_keywords": [],
        "is_distractor": True
    },
    {
        "id": "Q52",
        "category": "Distractors & Out-of-Domain",
        "query": "Can you give me a recipe for authentic Italian Margherita pizza?",
        "expected_service": "NONE",
        "expected_keywords": [],
        "is_distractor": True
    },
    {
        "id": "Q53",
        "category": "Distractors & Out-of-Domain",
        "query": "Who won the FIFA World Cup football championship in 2022?",
        "expected_service": "NONE",
        "expected_keywords": [],
        "is_distractor": True
    },
    {
        "id": "Q54",
        "category": "Distractors & Out-of-Domain",
        "query": "Explain quantum entanglement mechanics using Schrödinger wave equations",
        "expected_service": "NONE",
        "expected_keywords": [],
        "is_distractor": True
    },
    {
        "id": "Q55",
        "category": "Distractors & Out-of-Domain",
        "query": "Best recommendations for vintage acoustic guitar strings under 50 dollars",
        "expected_service": "NONE",
        "expected_keywords": [],
        "is_distractor": True
    }
]


# =============================================================================
# EVALUATION METRICS ENGINE
# =============================================================================

def is_match(retrieved_doc: Dict[str, Any], test_case: Dict[str, Any]) -> bool:
    """Evaluates whether retrieved doc matches expected ground-truth."""
    if test_case["is_distractor"]:
        return False  # Distractors should retrieve 0 documents

    title = retrieved_doc.get("title", "")
    text = retrieved_doc.get("text", "")
    service = retrieved_doc.get("service_type", "")

    # Check if expected keywords or service match
    for kw in test_case["expected_keywords"]:
        if kw.lower() in title.lower() or kw.lower() in text.lower():
            return True

    if test_case["expected_service"] != "general" and test_case["expected_service"] == service:
        return True

    return False


def evaluate_retrieval(
    results: List[Dict[str, Any]],
    test_case: Dict[str, Any],
    top_k: int = 3
) -> Dict[str, Any]:
    """Computes Precision@1, Precision@3, Recall@3, MRR, and Noise Filtering."""
    is_distractor = test_case["is_distractor"]

    # If distractor query:
    if is_distractor:
        if len(results) == 0:
            # Correctly rejected noise!
            return {
                "precision_at_1": 1.0,
                "precision_at_3": 1.0,
                "recall_at_3": 1.0,
                "mrr": 1.0,
                "noise_rejected": True,
                "hallucination": False
            }
        else:
            # Hallucinated / false positive
            return {
                "precision_at_1": 0.0,
                "precision_at_3": 0.0,
                "recall_at_3": 0.0,
                "mrr": 0.0,
                "noise_rejected": False,
                "hallucination": True
            }

    # Standard positive test case:
    if not results:
        return {
            "precision_at_1": 0.0,
            "precision_at_3": 0.0,
            "recall_at_3": 0.0,
            "mrr": 0.0,
            "noise_rejected": False,
            "hallucination": False
        }

    # Precision @ 1
    p1 = 1.0 if is_match(results[0], test_case) else 0.0

    # Precision @ K & Recall @ K
    matches_in_k = 0
    first_match_rank = None

    for rank, doc in enumerate(results[:top_k]):
        if is_match(doc, test_case):
            matches_in_k += 1
            if first_match_rank is None:
                first_match_rank = rank + 1

    pk = matches_in_k / float(min(top_k, len(results))) if results else 0.0
    rk = 1.0 if matches_in_k > 0 else 0.0
    mrr = (1.0 / first_match_rank) if first_match_rank else 0.0

    return {
        "precision_at_1": p1,
        "precision_at_3": pk,
        "recall_at_3": rk,
        "mrr": mrr,
        "noise_rejected": False,
        "hallucination": False
    }


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

def run_rag_benchmark() -> Dict[str, Any]:
    print("=" * 80)
    print("🚀 EXECUTING 55-QUERY EMPIRICAL RAG BENCHMARK MATRIX")
    print("=" * 80)

    docs = load_knowledge_base_documents()
    print(f"Loaded {len(docs)} knowledge base runbook sections.\n")

    print("1. Initializing Baseline Naive Semantic RAG...")
    naive_rag = NaiveSemanticRetriever(docs)

    print("2. Initializing Standard Hybrid RAG (BM25 + Dense RRF)...")
    hybrid_rag = HybridRRFRetriever(docs)

    print("3. Initializing Hyper-Optimized Semantic RAG (Cross-Encoder + HyDE)...")
    hyper_rag = HyperOptimizedSemanticRetriever(docs)

    pipelines = [
        ("Naive Semantic RAG", naive_rag),
        ("Standard Hybrid RAG", hybrid_rag),
        ("Hyper-Optimized Semantic RAG", hyper_rag)
    ]

    benchmark_records = []
    summary_stats = {}

    for pipe_name, pipeline in pipelines:
        print(f"\nEvaluating: {pipe_name} across {len(BENCHMARK_DATASET)} queries...")
        
        p1_list = []
        p3_list = []
        r3_list = []
        mrr_list = []
        latencies = []
        noise_rejections = 0
        hallucinations = 0

        # Evaluate positive queries & distractors
        for item in BENCHMARK_DATASET:
            q = item["query"]
            t_start = time.perf_counter()
            results = pipeline.retrieve(q, top_k=3)
            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            latencies.append(elapsed_ms)

            eval_res = evaluate_retrieval(results, item, top_k=3)
            p1_list.append(eval_res["precision_at_1"])
            p3_list.append(eval_res["precision_at_3"])
            r3_list.append(eval_res["recall_at_3"])
            mrr_list.append(eval_res["mrr"])

            if eval_res["noise_rejected"]:
                noise_rejections += 1
            if eval_res["hallucination"]:
                hallucinations += 1

            # Top result details for record
            top_title = results[0]["title"] if results else "NONE (Filtered)"
            top_score = results[0]["score"] if results else 0.0

            benchmark_records.append({
                "pipeline": pipe_name,
                "query_id": item["id"],
                "category": item["category"],
                "query": q,
                "is_distractor": item["is_distractor"],
                "precision_at_1": eval_res["precision_at_1"],
                "precision_at_3": eval_res["precision_at_3"],
                "recall_at_3": eval_res["recall_at_3"],
                "mrr": eval_res["mrr"],
                "latency_ms": elapsed_ms,
                "top_title": top_title,
                "top_score": top_score
            })

        summary_stats[pipe_name] = {
            "mean_precision_at_1": float(np.mean(p1_list)),
            "mean_precision_at_3": float(np.mean(p3_list)),
            "mean_recall_at_3": float(np.mean(r3_list)),
            "mean_mrr": float(np.mean(mrr_list)),
            "latency_mean_ms": float(np.mean(latencies)),
            "latency_p50_ms": float(np.percentile(latencies, 50)),
            "latency_p90_ms": float(np.percentile(latencies, 90)),
            "latency_p99_ms": float(np.percentile(latencies, 99)),
            "noise_rejection_rate": float(noise_rejections / 5.0),  # 5 distractors total
            "hallucination_count": hallucinations
        }

    # Save to JSON
    output_json_path = os.path.join(os.path.dirname(__file__), "rag_benchmark_results.json")
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary_stats,
            "records": benchmark_records
        }, f, indent=2)

    # Save to CSV
    output_csv_path = os.path.join(os.path.dirname(__file__), "rag_benchmark_results.csv")
    if benchmark_records:
        keys = benchmark_records[0].keys()
        with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(benchmark_records)

    # Print Formatted Executive Table
    print("\n" + "=" * 90)
    print("📊 EMPIRICAL BENCHMARK SUMMARY RESULTS")
    print("=" * 90)
    header = f"{'Architecture':<30} | {'P@1':<7} | {'P@3':<7} | {'Recall@3':<8} | {'MRR':<7} | {'Noise Rej':<10} | {'P50 (ms)':<8}"
    print(header)
    print("-" * 90)
    for pipe, stats in summary_stats.items():
        row = (
            f"{pipe:<30} | "
            f"{stats['mean_precision_at_1']*100:>5.1f}% | "
            f"{stats['mean_precision_at_3']*100:>5.1f}% | "
            f"{stats['mean_recall_at_3']*100:>7.1f}% | "
            f"{stats['mean_mrr']:>7.3f} | "
            f"{stats['noise_rejection_rate']*100:>8.1f}% | "
            f"{stats['latency_p50_ms']:>6.1f}ms"
        )
        print(row)
    print("=" * 90)
    print(f"Results exported to:\n - {output_json_path}\n - {output_csv_path}")

    return summary_stats


if __name__ == "__main__":
    run_rag_benchmark()

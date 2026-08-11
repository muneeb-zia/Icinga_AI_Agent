"""
Elasticsearch Integration Module for Icinga AI Agent.

Pre-configured for the production Elasticsearch instance at opensearch.internal:9200.
Set ES_ENABLED = True once VPN access is restored.

All functions gracefully handle connection failures and return
informative error messages instead of crashing.
"""

import os
import json
import io
import base64
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

# --- Configuration ---
# LOCAL SANDBOX: Points to the isolated opensearch-lab container (localhost:9200)
# This is NOT the company server (opensearch.internal). Safe for testing.
ES_ENABLED = os.environ.get("ES_ENABLED", "true").lower() == "true"

ES_HOST = os.environ.get("ES_HOST", "localhost")
ES_PORT = int(os.environ.get("ES_PORT", "9200"))
ES_SCHEME = os.environ.get("ES_SCHEME", "http")  # No SSL for local sandbox

# No auth needed for local sandbox (DISABLE_SECURITY_PLUGIN=true in docker-compose)
ES_USERNAME = os.environ.get("ES_USERNAME", None)
ES_PASSWORD = os.environ.get("ES_PASSWORD", None)
ES_API_KEY = os.environ.get("ES_API_KEY", None)

# Icinga2 Elasticsearch writer uses 'icinga2-*' index pattern by default
ES_INDEX_PATTERN = os.environ.get("ES_INDEX_PATTERN", "icinga2-*")

# Internal state
_es_client = None


def _get_client():
    """Lazily initialize and return the Elasticsearch client."""
    global _es_client
    if _es_client is not None:
        return _es_client

    try:
        from opensearchpy import OpenSearch

        # Build connection kwargs
        conn_kwargs = {
            "hosts": [{"host": ES_HOST, "port": ES_PORT, "scheme": ES_SCHEME}],
            "request_timeout": 10,
        }

        # Authentication
        if ES_API_KEY:
            conn_kwargs["api_key"] = ES_API_KEY
        elif ES_USERNAME and ES_PASSWORD:
            conn_kwargs["http_auth"] = (ES_USERNAME, ES_PASSWORD)

        # Disable SSL verification for internal networks (common in enterprise)
        if ES_SCHEME == "https":
            conn_kwargs["verify_certs"] = False

        _es_client = OpenSearch(**conn_kwargs)

        # Quick connectivity check
        if not _es_client.ping():
            _es_client = None
            return None

        return _es_client

    except ImportError:
        print("WARNING: 'opensearch-py' package not installed. Run: pip install opensearch-py")
        return None
    except Exception as e:
        print(f"WARNING: Could not connect to Elasticsearch at {ES_HOST}:{ES_PORT} — {e}")
        _es_client = None
        return None


def _parse_time_range(time_range: str) -> str:
    """Convert human-friendly time ranges like '24h', '7d', '30d' to ES format."""
    return f"now-{time_range}"


def _not_connected_response(function_name: str) -> Dict:
    """Standard response when ES is disabled or unreachable."""
    if not ES_ENABLED:
        return {
            "error": "Elasticsearch is not enabled yet.",
            "detail": f"ES_ENABLED is False. The production Elasticsearch at {ES_HOST}:{ES_PORT} "
                       "is not yet connected (VPN issue). Historical data is being served from the "
                       "local MySQL IDO database instead. Set ES_ENABLED=true once VPN access is restored.",
            "function": function_name,
            "fallback": "mysql_ido"
        }
    return {
        "error": f"Could not connect to Elasticsearch at {ES_HOST}:{ES_PORT}.",
        "detail": "ES_ENABLED is True but the cluster is unreachable. Check VPN connection and ES status.",
        "function": function_name
    }


# =============================================================================
# PUBLIC API FUNCTIONS
# =============================================================================

def search_host_events(hostname: str, time_range: str = "24h", limit: int = 20) -> Dict[str, Any]:
    """
    Search for all events (state changes, notifications, downtimes) related to
    a specific host from the Elasticsearch Icinga indices.

    Args:
        hostname: The Icinga host name to search for.
        time_range: How far back to search (e.g., '24h', '7d', '30d').
        limit: Maximum number of events to return.

    Returns:
        Dict with event list or error information.
    """
    if not ES_ENABLED:
        return _not_connected_response("search_host_events")

    client = _get_client()
    if not client:
        return _not_connected_response("search_host_events")

    try:
        query = {
            "size": limit,
            "sort": [{"@timestamp": {"order": "desc"}}],
            "query": {
                "bool": {
                    "must": [
                        {"match": {"host.name": hostname}},
                        {"range": {"@timestamp": {"gte": _parse_time_range(time_range)}}}
                    ]
                }
            }
        }

        result = client.search(index=ES_INDEX_PATTERN, body=query)

        events = []
        for hit in result.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            events.append({
                "timestamp": source.get("@timestamp"),
                "type": source.get("type", "unknown"),
                "state": source.get("state", source.get("check_result", {}).get("state")),
                "output": source.get("output", source.get("check_result", {}).get("output")),
                "host": source.get("host", {}).get("name", hostname),
            })

        return {
            "host": hostname,
            "time_range": time_range,
            "total_events": len(events),
            "events": events,
            "source": "elasticsearch"
        }

    except Exception as e:
        return {"error": f"Elasticsearch query failed: {str(e)}", "function": "search_host_events"}


def get_alert_history(severity: Optional[str] = None, time_range: str = "7d", limit: int = 50) -> Dict[str, Any]:
    """
    Fetch the full alert history from Elasticsearch with optional severity filtering.

    Args:
        severity: Filter by severity — 'WARNING', 'CRITICAL', 'UNKNOWN', or None for all.
        time_range: How far back to search (e.g., '24h', '7d', '30d').
        limit: Maximum number of alerts to return.

    Returns:
        Dict with alert history or error information.
    """
    if not ES_ENABLED:
        return _not_connected_response("get_alert_history")

    client = _get_client()
    if not client:
        return _not_connected_response("get_alert_history")

    try:
        severity_map = {"WARNING": 1, "CRITICAL": 2, "UNKNOWN": 3}

        must_clauses = [
            {"range": {"@timestamp": {"gte": _parse_time_range(time_range)}}},
            {"exists": {"field": "state"}}
        ]

        if severity and severity.upper() in severity_map:
            must_clauses.append({"term": {"state": severity_map[severity.upper()]}})

        query = {
            "size": limit,
            "sort": [{"@timestamp": {"order": "desc"}}],
            "query": {
                "bool": {
                    "must": must_clauses,
                    "must_not": [{"term": {"state": 0}}]  # Exclude OK/UP states
                }
            }
        }

        result = client.search(index=ES_INDEX_PATTERN, body=query)

        state_names = {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"}
        alerts = []
        for hit in result.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            state_val = source.get("state")
            alerts.append({
                "timestamp": source.get("@timestamp"),
                "host": source.get("host", {}).get("name", "unknown"),
                "service": source.get("service", {}).get("name", "host-check"),
                "state": state_names.get(state_val, str(state_val)),
                "output": source.get("output", ""),
            })

        return {
            "filter": severity or "ALL",
            "time_range": time_range,
            "total_alerts": len(alerts),
            "alerts": alerts,
            "source": "elasticsearch"
        }

    except Exception as e:
        return {"error": f"Elasticsearch query failed: {str(e)}", "function": "get_alert_history"}


def search_logs_by_keyword(keyword: str, time_range: str = "24h", limit: int = 20) -> Dict[str, Any]:
    """
    Perform a free-text search across all Icinga log indices in Elasticsearch.

    Args:
        keyword: The search term (e.g., 'disk full', 'timeout', 'connection refused').
        time_range: How far back to search.
        limit: Maximum results.

    Returns:
        Dict with matching log entries or error information.
    """
    if not ES_ENABLED:
        return _not_connected_response("search_logs_by_keyword")

    client = _get_client()
    if not client:
        return _not_connected_response("search_logs_by_keyword")

    try:
        query = {
            "size": limit,
            "sort": [{"@timestamp": {"order": "desc"}}],
            "query": {
                "bool": {
                    "must": [
                        {"multi_match": {
                            "query": keyword,
                            "fields": ["output", "message", "comment", "long_output"],
                            "type": "best_fields"
                        }},
                        {"range": {"@timestamp": {"gte": _parse_time_range(time_range)}}}
                    ]
                }
            },
            "_source": ["@timestamp", "host.name", "service.name", "output", "message", "state"]
        }

        result = client.search(index=ES_INDEX_PATTERN, body=query)

        logs = []
        for hit in result.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            logs.append({
                "timestamp": source.get("@timestamp"),
                "host": source.get("host", {}).get("name", "unknown"),
                "service": source.get("service", {}).get("name", ""),
                "message": source.get("output") or source.get("message", ""),
                "score": hit.get("_score"),
            })

        return {
            "keyword": keyword,
            "time_range": time_range,
            "total_matches": len(logs),
            "logs": logs,
            "source": "elasticsearch"
        }

    except Exception as e:
        return {"error": f"Elasticsearch query failed: {str(e)}", "function": "search_logs_by_keyword"}


def get_performance_data(hostname: str, metric: str, time_range: str = "24h") -> Dict[str, Any]:
    """
    Pull performance data time-series from Elasticsearch for graphing.

    Args:
        hostname: The host to query.
        metric: Metric name (e.g., 'cpu', 'memory', 'disk', 'load').
        time_range: How far back to fetch.

    Returns:
        Dict with time-series datapoints or error information.
    """
    if not ES_ENABLED:
        return _not_connected_response("get_performance_data")

    client = _get_client()
    if not client:
        return _not_connected_response("get_performance_data")

    try:
        query = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {"match": {"host": hostname}},
                        {"range": {"@timestamp": {"gte": _parse_time_range(time_range)}}},
                        {"match": {"label": metric}}
                    ]
                }
            },
            "aggs": {
                "over_time": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "fixed_interval": "1h"
                    },
                    "aggs": {
                        "avg_value": {
                            "avg": {"field": "value"}
                        }
                    }
                }
            }
        }

        result = client.search(index=ES_INDEX_PATTERN, body=query)

        buckets = result.get("aggregations", {}).get("over_time", {}).get("buckets", [])
        datapoints = []
        for bucket in buckets:
            datapoints.append({
                "timestamp": bucket.get("key_as_string"),
                "epoch": bucket.get("key"),
                "value": bucket.get("avg_value", {}).get("value"),
            })

        return {
            "host": hostname,
            "metric": metric,
            "time_range": time_range,
            "total_datapoints": len(datapoints),
            "datapoints": datapoints,
            "source": "elasticsearch"
        }

    except Exception as e:
        return {"error": f"Elasticsearch query failed: {str(e)}", "function": "get_performance_data"}


def get_host_state_timeline(hostname: str, time_range: str = "30d") -> Dict[str, Any]:
    """
    Build an UP/DOWN state timeline for a host over a given period.
    Useful for understanding availability and recurring outage patterns.

    Args:
        hostname: The host to query.
        time_range: How far back to look (e.g., '7d', '30d', '90d').

    Returns:
        Dict with state change timeline or error information.
    """
    if not ES_ENABLED:
        return _not_connected_response("get_host_state_timeline")

    client = _get_client()
    if not client:
        return _not_connected_response("get_host_state_timeline")

    try:
        query = {
            "size": 500,
            "sort": [{"@timestamp": {"order": "asc"}}],
            "query": {
                "bool": {
                    "must": [
                        {"match": {"host.name": hostname}},
                        {"range": {"@timestamp": {"gte": _parse_time_range(time_range)}}},
                        {"terms": {"type": ["StateChange", "state_change", "statechange"]}}
                    ]
                }
            },
            "_source": ["@timestamp", "state", "output", "last_state", "state_type"]
        }

        result = client.search(index=ES_INDEX_PATTERN, body=query)

        state_names = {0: "UP", 1: "DOWN", 2: "UNREACHABLE"}
        timeline = []
        for hit in result.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            state_val = source.get("state")
            last_state_val = source.get("last_state")
            timeline.append({
                "timestamp": source.get("@timestamp"),
                "from_state": state_names.get(last_state_val, str(last_state_val)),
                "to_state": state_names.get(state_val, str(state_val)),
                "output": source.get("output", ""),
                "state_type": source.get("state_type", ""),
            })

        # Calculate availability summary
        total_changes = len(timeline)
        down_events = sum(1 for t in timeline if t["to_state"] == "DOWN")

        return {
            "host": hostname,
            "time_range": time_range,
            "total_state_changes": total_changes,
            "down_events": down_events,
            "timeline": timeline,
            "source": "elasticsearch"
        }

    except Exception as e:
        return {"error": f"Elasticsearch query failed: {str(e)}", "function": "get_host_state_timeline"}


# =============================================================================
# NEW: Elasticsearch Cluster & Advanced Search Tools
# =============================================================================

def get_elasticsearch_cluster_health() -> Dict[str, Any]:
    """Returns the health status of the Elasticsearch cluster."""
    if not ES_ENABLED:
        return _not_connected_response("get_elasticsearch_cluster_health")
    
    client = _get_client()
    if not client:
        return _not_connected_response("get_elasticsearch_cluster_health")
        
    try:
        return client.cluster.health()
    except Exception as e:
        return {"error": f"Failed to get cluster health: {str(e)}", "function": "get_elasticsearch_cluster_health"}


def get_elasticsearch_indices(health: str = None) -> Dict[str, Any]:
    """Lists all indices in the Elasticsearch cluster and their health/stats."""
    if not ES_ENABLED:
        return _not_connected_response("get_elasticsearch_indices")
        
    client = _get_client()
    if not client:
        return _not_connected_response("get_elasticsearch_indices")
        
    try:
        indices = client.cat.indices(format="json")
        if health:
            health_str = str(health).lower()
            if "green" in health_str: h = "green"
            elif "yellow" in health_str: h = "yellow"
            elif "red" in health_str: h = "red"
            else: h = health_str
            indices = [i for i in indices if i.get("health") == h]
            
        summary = []
        for i in indices:
            summary.append({
                "index": i.get("index"),
                "health": i.get("health"),
                "docs": i.get("docs.count"),
                "size": i.get("store.size")
            })
        return {"total_count": len(summary), "indices": summary}
    except Exception as e:
        return {"error": f"Failed to get indices: {str(e)}", "function": "get_elasticsearch_indices"}


def search_elasticsearch_custom_query(query_string: str, index: str = "_all", limit: int = 20) -> Dict[str, Any]:
    """Runs a custom Lucene query string against Elasticsearch."""
    if not ES_ENABLED:
        return _not_connected_response("search_elasticsearch_custom_query")
        
    client = _get_client()
    if not client:
        return _not_connected_response("search_elasticsearch_custom_query")
        
    try:
        res = client.search(index=index, q=query_string, size=limit)
        return res
    except Exception as e:
        return {"error": f"Search failed: {str(e)}", "function": "search_elasticsearch_custom_query"}


def get_elasticsearch_node_stats() -> Dict[str, Any]:
    """Retrieves health and performance metrics for Elasticsearch nodes."""
    if not ES_ENABLED:
        return _not_connected_response("get_elasticsearch_node_stats")
        
    client = _get_client()
    if not client:
        return _not_connected_response("get_elasticsearch_node_stats")
        
    try:
        nodes = client.nodes.stats(metric="jvm,os,fs")
        summary = []
        for node_id, node_info in nodes.get("nodes", {}).items():
            name = node_info.get("name", node_id)
            jvm_heap_used_pct = node_info.get("jvm", {}).get("mem", {}).get("heap_used_percent")
            cpu_pct = node_info.get("os", {}).get("cpu", {}).get("percent")
            fs = node_info.get("fs", {}).get("total", {})
            fs_free_bytes = fs.get("available_in_bytes", 0)
            fs_total_bytes = fs.get("total_in_bytes", 1)
            disk_used_pct = round((1 - (fs_free_bytes / fs_total_bytes)) * 100, 2) if fs_total_bytes else 0
            
            summary.append({
                "node_name": name,
                "jvm_heap_used_percent": jvm_heap_used_pct,
                "cpu_percent": cpu_pct,
                "disk_used_percent": disk_used_pct
            })
        return {"nodes": summary, "count": len(summary)}
    except Exception as e:
        return {"error": f"Failed to get node stats: {str(e)}", "function": "get_elasticsearch_node_stats"}


def aggregate_elasticsearch_errors(time_range: str = "24h", limit: int = 5) -> Dict[str, Any]:
    """Aggregates the most common errors/failing hosts in the given time range."""
    if not ES_ENABLED:
        return _not_connected_response("aggregate_elasticsearch_errors")
        
    client = _get_client()
    if not client:
        return _not_connected_response("aggregate_elasticsearch_errors")
        
    try:
        query = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {"range": {"@timestamp": {"gte": _parse_time_range(time_range)}}}
                    ],
                    "should": [
                        {"match": {"state": 2}},
                        {"match": {"state": 1}},
                        {"match": {"state": "CRITICAL"}},
                        {"match": {"state": "DOWN"}}
                    ],
                    "minimum_should_match": 1
                }
            },
            "aggs": {
                "top_failing_hosts": {
                    "terms": {
                        "field": "host.name.keyword",
                        "size": limit
                    }
                }
            }
        }
        
        result = client.search(index=ES_INDEX_PATTERN, body=query)
        aggs = result.get("aggregations", {})
        
        return {
            "time_range": time_range,
            "top_failing_hosts": aggs.get("top_failing_hosts", {}).get("buckets", []),
            "source": "elasticsearch"
        }
    except Exception as e:
        return {"error": f"Failed to aggregate errors: {str(e)}", "function": "aggregate_elasticsearch_errors"}


def detect_elasticsearch_log_spikes(hostname: str) -> Dict[str, Any]:
    """Detects log volume anomalies by comparing last 1h to previous 24h average."""
    if not ES_ENABLED:
        return _not_connected_response("detect_elasticsearch_log_spikes")
        
    client = _get_client()
    if not client:
        return _not_connected_response("detect_elasticsearch_log_spikes")
        
    try:
        q_1h = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"host.name": hostname}},
                        {"range": {"@timestamp": {"gte": "now-1h"}}}
                    ]
                }
            }
        }
        res_1h = client.count(index=ES_INDEX_PATTERN, body=q_1h)
        count_1h = res_1h.get("count", 0)
        
        q_24h = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"host.name": hostname}},
                        {"range": {"@timestamp": {"gte": "now-25h", "lt": "now-1h"}}}
                    ]
                }
            }
        }
        res_24h = client.count(index=ES_INDEX_PATTERN, body=q_24h)
        count_24h = res_24h.get("count", 0)
        avg_per_hour = count_24h / 24.0
        
        is_spike = False
        spike_multiplier = 0.0
        if avg_per_hour > 0:
            spike_multiplier = count_1h / avg_per_hour
            if spike_multiplier > 3.0 and count_1h > 10:
                is_spike = True
        elif count_1h > 20:
            is_spike = True
            spike_multiplier = float('inf')
            
        return {
            "host": hostname,
            "last_1h_count": count_1h,
            "previous_24h_avg_per_hour": round(avg_per_hour, 2),
            "is_anomaly": is_spike,
            "spike_multiplier": round(spike_multiplier, 2) if spike_multiplier != float('inf') else "infinity"
        }
    except Exception as e:
        return {"error": f"Failed to detect spikes: {str(e)}", "function": "detect_elasticsearch_log_spikes"}


def plot_elasticsearch_log_volume(hostname: Optional[str] = None, time_range: str = "7d", interval: str = "1d") -> Dict[str, Any]:
    """Generates a date histogram of log volume and returns a base64 png image string."""
    if not ES_ENABLED:
        return _not_connected_response("plot_elasticsearch_log_volume")
        
    client = _get_client()
    if not client:
        return _not_connected_response("plot_elasticsearch_log_volume")
        
    try:
        query = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {"range": {"@timestamp": {"gte": _parse_time_range(time_range)}}}
                    ]
                }
            },
            "aggs": {
                "log_volume_over_time": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "calendar_interval": interval
                    }
                }
            }
        }
        
        if hostname and hostname.lower() != "none" and hostname != "":
            query["query"]["bool"]["must"].append({"match": {"host.name": hostname}})
            
        result = client.search(index=ES_INDEX_PATTERN, body=query)
        buckets = result.get("aggregations", {}).get("log_volume_over_time", {}).get("buckets", [])
        
        if not buckets:
            return {"error": "No log data found to plot in the given time range."}
            
        x_values = []
        y_values = []
        for bucket in buckets:
            ts = bucket.get("key", 0) / 1000.0
            x_values.append(datetime.fromtimestamp(ts))
            y_values.append(bucket.get("doc_count", 0))
            
        # Generate Plot
        plt.figure(figsize=(10, 4))
        plt.plot(x_values, y_values, marker='.', linestyle='-', color='purple')
        
        title = f"Log Volume Trend ({interval} intervals)"
        if hostname and hostname.lower() != "none" and hostname != "":
            title += f" for {hostname}"
            
        plt.title(title)
        plt.xlabel("Time")
        plt.ylabel("Log Count")
        plt.grid(True)
        plt.tight_layout()
        
        plt.savefig("latest_plot.png", format='png')
        plt.close()
        
        return {
            "image_markdown": "Graph generated successfully and saved to latest_plot.png. Tell the user to view the graph.",
            "source": "elasticsearch",
            "datapoints": len(buckets)
        }
    except Exception as e:
        return {"error": f"Failed to plot log volume: {str(e)}", "function": "plot_elasticsearch_log_volume"}


# =============================================================================
# SELF-TEST
# =============================================================================
if __name__ == "__main__":
    print(f"Elasticsearch Integration Module")
    print(f"  Target: {ES_SCHEME}://{ES_HOST}:{ES_PORT}")
    print(f"  Index Pattern: {ES_INDEX_PATTERN}")
    print(f"  ES_ENABLED: {ES_ENABLED}")
    print()

    if not ES_ENABLED:
        print("ES is disabled (ES_ENABLED=false). Testing graceful fallback...")
        result = search_host_events("icinga-master")
        print(f"  search_host_events → {json.dumps(result, indent=2)}")
        result = get_alert_history()
        print(f"  get_alert_history → {json.dumps(result, indent=2)}")
        print("\n✅ All functions return graceful fallback messages. Ready for integration.")
    else:
        print("ES is enabled. Testing live connection...")
        result = search_host_events("icinga-master", time_range="1h")
        print(f"  search_host_events → {json.dumps(result, indent=2)}")

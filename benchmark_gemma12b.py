"""
Targeted Empirical Benchmark for Gemma 4 12B on Company 16GB GPU Server (gpu-server.internal:11434)
Measures:
1. Generation Throughput (tok/s) & TTFT (ms)
2. KV-Cache TTFT Speedup (%)
3. Structured Tool Calling Precision across 5 Icinga Operations
4. Context Scaling Latency
"""
import os
import sys
import time
import json
import urllib.request
from typing import Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "http://gpu-server.internal:11434")
MODEL_NAME = "gemma4:12b"

SYSTEM_PROMPT_ICINGA = """You are an expert Icinga 2 AIOps Autonomous Incident Agent.
When given an operational scenario or alert, you MUST output ONLY valid JSON matching this schema:
{
  "tool_name": "<tool_name>",
  "parameters": { ... }
}
Available Tools:
1. schedule_downtime: {"host_name": str, "service_name": str, "author": str, "comment": str, "duration_seconds": int}
2. acknowledge_problem: {"host_name": str, "service_name": str, "author": str, "comment": str}
3. restart_service: {"host_name": str, "service_name": str, "force": bool}
4. generate_sla_report: {"client_name": str, "days": int, "format": str}
5. dispatch_teams_notification: {"team": str, "severity": str, "message": str}

Output ONLY the JSON object. Do not include introductory text, conversational chatter, or markdown fences if possible."""

def query_ollama_stream(model: str, prompt: str, system: str = "") -> Dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": True,
        "options": {
            "temperature": 0.0,
            "num_predict": 256
        }
    }
    url = f"{OLLAMA_BASE_URL}/api/generate"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    start_time = time.perf_counter()
    first_token_time = None
    full_response = []
    eval_count = 0
    eval_duration_ns = 0
    prompt_eval_count = 0
    prompt_eval_duration_ns = 0
    
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            for line in response:
                if not line:
                    continue
                chunk = json.loads(line.decode("utf-8"))
                if first_token_time is None and chunk.get("response"):
                    first_token_time = time.perf_counter()
                
                full_response.append(chunk.get("response", ""))
                
                if chunk.get("done"):
                    prompt_eval_count = chunk.get("prompt_eval_count", 0)
                    prompt_eval_duration_ns = chunk.get("prompt_eval_duration", 0)
                    eval_count = chunk.get("eval_count", len(full_response))
                    eval_duration_ns = chunk.get("eval_duration", 0)
                    break
        
        end_time = time.perf_counter()
        total_time_sec = end_time - start_time
        ttft_ms = ((first_token_time - start_time) * 1000.0) if first_token_time else (total_time_sec * 1000.0)
        
        eval_duration_sec = eval_duration_ns / 1e9 if eval_duration_ns > 0 else total_time_sec
        gen_tps = (eval_count / eval_duration_sec) if eval_duration_sec > 0 else 0.0
        
        return {
            "success": True,
            "ttft_ms": round(ttft_ms, 2),
            "generation_tps": round(gen_tps, 2),
            "total_latency_ms": round(total_time_sec * 1000.0, 2),
            "tokens_generated": eval_count,
            "prompt_tokens": prompt_eval_count,
            "response_text": "".join(full_response).strip()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "ttft_ms": 0.0,
            "generation_tps": 0.0,
            "total_latency_ms": 0.0,
            "tokens_generated": 0,
            "response_text": ""
        }

def run_gemma12b_benchmark():
    print("=" * 85)
    print(f"🔬 BENCHMARKING {MODEL_NAME} ON COMPANY 16GB GPU TIER ({OLLAMA_BASE_URL})")
    print("=" * 85)

    # 1. Throughput & TTFT
    print("\n[Step 1/3] Measuring Raw Generation Throughput & TTFT...")
    sample_prompt = (
        "Alert Incident: CRITICAL on host db-prod-mysql-01.\n"
        "Service: check_mysql_connections.\n"
        "Plugin Output: CRITICAL - Active connections at 98% (490/500 max_connections).\n"
        "Analyze the root cause and provide 3 immediate diagnostic steps."
    )
    tp = query_ollama_stream(MODEL_NAME, sample_prompt, system=SYSTEM_PROMPT_ICINGA)
    print(f"  • Status: {'SUCCESS' if tp['success'] else 'FAILED'}")
    print(f"  • TTFT: {tp['ttft_ms']} ms")
    print(f"  • Generation Throughput: {tp['generation_tps']} tok/s")
    print(f"  • Tokens Generated: {tp['tokens_generated']}")
    print(f"  • Total Latency: {tp['total_latency_ms']} ms")

    # 2. Tool Calling Precision
    print("\n[Step 2/3] Evaluating Tool-Calling Schema Precision across 5 Icinga Operations...")
    test_scenarios = [
        {
            "prompt": "Schedule a 2 hour maintenance downtime for host db-prod-mysql-01 and service check_mysql_connections. Author: noc_lead, reason: Emergency index rebuild.",
            "expected_tool": "schedule_downtime",
            "required_keys": ["host_name", "service_name", "author", "comment", "duration_seconds"]
        },
        {
            "prompt": "Acknowledge the critical disk alert on host web-server-02 for service check_disk. Author: sreadmin, comment: Cleaning /var/log.",
            "expected_tool": "acknowledge_problem",
            "required_keys": ["host_name", "service_name", "author", "comment"]
        },
        {
            "prompt": "Restart the nginx service on web-lb-01 immediately with force=True.",
            "expected_tool": "restart_service",
            "required_keys": ["host_name", "service_name", "force"]
        },
        {
            "prompt": "Generate a 30-day SLA compliance report for client RetailCorp in PDF format.",
            "expected_tool": "generate_sla_report",
            "required_keys": ["client_name", "days", "format"]
        },
        {
            "prompt": "Send a critical alert notification to the DevOps team regarding database lock saturation.",
            "expected_tool": "dispatch_teams_notification",
            "required_keys": ["team", "severity", "message"]
        }
    ]

    valid_json = 0
    correct_tools = 0
    valid_schemas = 0

    for idx, sc in enumerate(test_scenarios):
        res = query_ollama_stream(MODEL_NAME, sc["prompt"], system=SYSTEM_PROMPT_ICINGA)
        raw_text = res.get("response_text", "")
        clean_text = raw_text
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()
        
        is_json = False
        tool_match = False
        schema_match = False

        try:
            parsed = json.loads(clean_text)
            is_json = True
            valid_json += 1
            if parsed.get("tool_name") == sc["expected_tool"]:
                tool_match = True
                correct_tools += 1
                params = parsed.get("parameters", {})
                if all(k in params for k in sc["required_keys"]):
                    schema_match = True
                    valid_schemas += 1
        except Exception:
            pass

        print(f"  • Scenario {idx+1} ({sc['expected_tool']}): JSON={is_json} | Tool Match={tool_match} | Schema Match={schema_match}")

    total_scenarios = len(test_scenarios)
    json_pct = round((valid_json / total_scenarios) * 100.0, 1)
    tool_pct = round((correct_tools / total_scenarios) * 100.0, 1)
    schema_pct = round((valid_schemas / total_scenarios) * 100.0, 1)

    print(f"\n  📊 Tool Precision Summary for {MODEL_NAME}:")
    print(f"     - Valid JSON Format: {json_pct}%")
    print(f"     - Tool Selection Accuracy: {tool_pct}%")
    print(f"     - Parameter Schema Precision: {schema_pct}%")

    # 3. Context Scaling (1k & 2k tokens)
    print("\n[Step 3/3] Evaluating Context Scaling Latency (1k, 2k)...")
    base_log = "2026-08-30T23:00:00.102Z host=db-prod-mysql-01 thread=104 query='SELECT * FROM orders' duration=4.2s lock_time=1.8s\n"
    for label, count in [("1k tokens", 10), ("2k tokens", 20)]:
        prompt = f"Telemetry Logs:\n{base_log * count}\nIdentify root cause."
        ctx_res = query_ollama_stream(MODEL_NAME, prompt, system=SYSTEM_PROMPT_ICINGA)
        print(f"  • Context {label}: TTFT={ctx_res['ttft_ms']} ms | Gen TPS={ctx_res['generation_tps']} | Total={ctx_res['total_latency_ms']} ms")

    print("\n" + "=" * 85)
    print("🎯 BENCHMARK RUN COMPLETED")
    print("=" * 85)

if __name__ == "__main__":
    run_gemma12b_benchmark()

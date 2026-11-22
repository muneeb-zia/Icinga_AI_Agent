"""
Targeted Empirical Benchmark Suite for Gemma 4 E4B on Company 16GB GPU Server (set COMPANY_GPU_URL / OLLAMA_URL)
=====================================================================================================
Comprehensive Evaluation across the 5 Core Pillar 2 Dimensions:
1. Generation Throughput (tok/s), Time-To-First-Token (TTFT ms), and Prompt Eval Throughput
2. Static KV-Cache / Prompt Caching Speedup (%)
3. Structured Tool-Calling Precision across 5 realistic Icinga 2 operations
4. Context Window Scaling Latency (1k, 2k, 4k, 8k tokens)
5. Concurrency Load Stress Curve (1, 2, 4 parallel operators, P50, P90, P99)
"""

import os
import sys
import time
import json
import csv
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

COMPANY_GPU_URL = os.environ.get("COMPANY_GPU_URL", "http://localhost:11434")
MODEL_NAME = "gemma4:e4b"

SYSTEM_PROMPT_ICINGA = """You are the Icinga Enterprise AIOps Autonomous Incident Agent.
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

Output ONLY the JSON object. Do not include markdown formatting or commentary."""

def query_gemma_stream(prompt: str, system: str = "") -> Dict[str, Any]:
    """Execute streaming HTTP request to Ollama measuring TTFT and generation TPS."""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "system": system,
        "stream": True,
        "options": {
            "temperature": 0.0,
            "num_predict": 256
        }
    }
    url = f"{COMPANY_GPU_URL}/api/generate"
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
                
                resp_token = chunk.get("response", "")
                if first_token_time is None and (resp_token or chunk.get("thinking")):
                    first_token_time = time.perf_counter()
                
                if resp_token:
                    full_response.append(resp_token)
                
                if chunk.get("done"):
                    prompt_eval_count = chunk.get("prompt_eval_count", 0)
                    prompt_eval_duration_ns = chunk.get("prompt_eval_duration", 0)
                    eval_count = chunk.get("eval_count", len(full_response))
                    eval_duration_ns = chunk.get("eval_duration", 0)
                    break
                    
        end_time = time.perf_counter()
        total_time_sec = end_time - start_time
        ttft_ms = ((first_token_time - start_time) * 1000.0) if first_token_time else (total_time_sec * 1000.0)
        
        eval_duration_sec = (eval_duration_ns / 1e9) if eval_duration_ns > 0 else total_time_sec
        gen_tps = (eval_count / eval_duration_sec) if eval_duration_sec > 0 else 0.0
        
        prompt_eval_sec = (prompt_eval_duration_ns / 1e9) if prompt_eval_duration_ns > 0 else 0.0
        prompt_tps = (prompt_eval_count / prompt_eval_sec) if prompt_eval_sec > 0 else 0.0
        
        return {
            "success": True,
            "ttft_ms": round(ttft_ms, 2),
            "generation_tps": round(gen_tps, 2),
            "prompt_eval_tps": round(prompt_tps, 2),
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
            "prompt_eval_tps": 0.0,
            "total_latency_ms": 0.0,
            "tokens_generated": 0,
            "prompt_tokens": 0,
            "response_text": ""
        }

def run_comprehensive_gemma4_e4b_benchmark():
    print("=" * 90)
    print(f"🚀 INITIATING FULL EMPIRICAL BENCHMARK FOR {MODEL_NAME.upper()}")
    print(f"   Target Hardware Tier: Company Enterprise 16GB GPU Server ({COMPANY_GPU_URL})")
    print("=" * 90)

    # 1. Throughput & TTFT
    print("\n[TEST 1/5] Measuring Generation Throughput (TPS) & Time-To-First-Token (TTFT)...")
    diagnostic_prompt = (
        "Alert Incident: CRITICAL on host db-prod-mysql-01.\n"
        "Service: check_mysql_connections.\n"
        "Plugin Output: CRITICAL - Active connections at 98% (490/500 max_connections). Thread pool saturated.\n"
        "Analyze the root cause and provide 3 immediate diagnostic steps."
    )
    tp = query_gemma_stream(diagnostic_prompt, system=SYSTEM_PROMPT_ICINGA)
    print(f"  • Status: {'✅ SUCCESS' if tp['success'] else '❌ FAILED'}")
    print(f"  • TTFT (Time-To-First-Token): {tp.get('ttft_ms', 0):.2f} ms")
    print(f"  • Generation Throughput:     {tp.get('generation_tps', 0):.2f} tok/s")
    print(f"  • Prompt Eval Throughput:    {tp.get('prompt_eval_tps', 0):.2f} tok/s")
    print(f"  • Total Request Latency:     {tp.get('total_latency_ms', 0):.2f} ms")
    print(f"  • Response Preview:          {tp.get('response_text', '')[:120]}...")

    # 2. KV-Cache & Prompt Caching
    print("\n[TEST 2/5] Benchmarking KV-Cache & Prompt Prefix Caching Speedup...")
    long_system = SYSTEM_PROMPT_ICINGA + "\n\nStandard Operational Runbook:\n" + ("NOC rule: Always inspect MySQL connection variables before restarting.\n" * 20)
    
    print("  • Executing Cold Request (uncached prefix)...")
    cold_res = query_gemma_stream("Acknowledge critical alert on host db-prod-mysql-01.", system=long_system)
    cold_ttft = cold_res.get("ttft_ms", 0)
    print(f"    - Cold TTFT: {cold_ttft:.2f} ms")
    
    print("  • Executing Warm Request (cached prefix)...")
    warm_res = query_gemma_stream("Schedule 60m downtime for host db-prod-mysql-01.", system=long_system)
    warm_ttft = warm_res.get("ttft_ms", 0)
    print(f"    - Warm TTFT: {warm_ttft:.2f} ms")
    
    speedup = ((cold_ttft - warm_ttft) / cold_ttft * 100.0) if cold_ttft > warm_ttft and cold_ttft > 0 else 0.0
    print(f"  • Prompt Caching TTFT Speedup: {speedup:.1f}%")

    # 3. Structured Tool Calling Precision across 5 Operational Scenarios
    print("\n[TEST 3/5] Testing Structured Tool Calling & JSON Schema Adherence (5 Scenarios)...")
    scenarios = [
        {
            "scenario": "Schedule 2-hour downtime on host db-prod-01 for MySQL index rebuild by admin.",
            "expected_tool": "schedule_downtime",
            "required_keys": ["host_name", "author", "comment", "duration_seconds"]
        },
        {
            "scenario": "Acknowledge critical disk space alert on host web-server-02 service disk_root by sreadmin with comment investigating log rotation.",
            "expected_tool": "acknowledge_problem",
            "required_keys": ["host_name", "service_name", "author", "comment"]
        },
        {
            "scenario": "Perform an immediate forced restart of service nginx on host web-lb-01.",
            "expected_tool": "restart_service",
            "required_keys": ["host_name", "service_name", "force"]
        },
        {
            "scenario": "Generate a 30-day SLA report for client RetailCorp in PDF format.",
            "expected_tool": "generate_sla_report",
            "required_keys": ["client_name", "days", "format"]
        },
        {
            "scenario": "Dispatch urgent notification to DevOps team: 'Payment gateway API failure rate exceeded 5% threshold, immediate triage required.'",
            "expected_tool": "dispatch_teams_notification",
            "required_keys": ["team", "severity", "message"]
        }
    ]

    valid_json_count = 0
    correct_tool_count = 0
    schema_match_count = 0

    for idx, sc in enumerate(scenarios, 1):
        prompt = f"Operational Event: {sc['scenario']}\nGenerate the required tool call JSON."
        call_res = query_gemma_stream(prompt, system=SYSTEM_PROMPT_ICINGA)
        raw_text = call_res.get("response_text", "").strip()
        
        # Clean any markdown code blocks if present
        clean_text = raw_text
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()
            
        is_valid_json = False
        parsed_json = {}
        try:
            parsed_json = json.loads(clean_text)
            is_valid_json = True
            valid_json_count += 1
        except Exception:
            pass

        tool_matched = False
        schema_matched = False
        if is_valid_json and isinstance(parsed_json, dict):
            if parsed_json.get("tool_name") == sc["expected_tool"]:
                tool_matched = True
                correct_tool_count += 1
            
            params = parsed_json.get("parameters", {})
            if all(k in params for k in sc["required_keys"]):
                schema_matched = True
                schema_match_count += 1

        print(f"  • Scenario {idx} ({sc['expected_tool']}): "
              f"JSON={'✅' if is_valid_json else '❌'} | "
              f"Tool={'✅' if tool_matched else '❌'} | "
              f"Schema={'✅' if schema_matched else '❌'}")
        if not is_valid_json or not tool_matched or not schema_matched:
            print(f"    [DEBUG Output]: {raw_text[:140]}...")

    tool_prec_pct = (schema_match_count / len(scenarios)) * 100.0
    print(f"  • Final Tool Schema Precision: {tool_prec_pct:.1f}% ({schema_match_count}/{len(scenarios)})")

    # 4. Context Window Scaling Latency
    print("\n[TEST 4/5] Context Window Scaling Latency Evaluation (1k, 2k, 4k, 8k tokens)...")
    context_results = []
    base_log = "2026-09-04T12:00:00Z [INFO] kernel: [1293.402] Out of memory: Kill process 2841 (mysqld) score 920 or sacrifice child.\n"
    for scale_label, multiplier in [("1k tokens", 10), ("2k tokens", 25), ("4k tokens", 50), ("8k tokens", 100)]:
        context_body = base_log * multiplier
        scaling_prompt = f"Correlate the following system syslog stream and identify failure point:\n{context_body}\n\nSummary:"
        sc_res = query_gemma_stream(scaling_prompt, system=SYSTEM_PROMPT_ICINGA)
        sc_tps = sc_res.get("generation_tps", 0)
        sc_ttft = sc_res.get("ttft_ms", 0)
        sc_total = sc_res.get("total_latency_ms", 0)
        print(f"  • Context {scale_label:>9}: TTFT = {sc_ttft:7.2f} ms | Gen TPS = {sc_tps:6.2f} tok/s | Total Latency = {sc_total:7.2f} ms")
        context_results.append({
            "context_label": scale_label,
            "approx_tokens": sc_res.get("prompt_tokens", 0),
            "ttft_ms": sc_ttft,
            "generation_tps": sc_tps,
            "total_latency_ms": sc_total
        })

    # 5. Concurrency Load Stress Curve
    print("\n[TEST 5/5] Multi-Tenant Concurrency Stress Curve (1, 2, and 4 Concurrent Operators)...")
    concurrency_results = {}
    test_user_prompt = "Critical incident on web-lb-01: service nginx unresponsive. Perform immediate diagnosis."
    
    for users in [1, 2, 4]:
        print(f"  • Simulating {users} concurrent operator request(s)...")
        latencies = []
        tokens_list = []
        batch_start = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=users) as executor:
            futures = [executor.submit(query_gemma_stream, test_user_prompt, SYSTEM_PROMPT_ICINGA) for _ in range(users)]
            for fut in as_completed(futures):
                res = fut.result()
                latencies.append(res.get("total_latency_ms", 0))
                tokens_list.append(res.get("tokens_generated", 0))
                
        batch_duration = time.perf_counter() - batch_start
        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.5)]
        p90 = latencies[min(int(len(latencies) * 0.9), len(latencies) - 1)]
        p99 = latencies[min(int(len(latencies) * 0.99), len(latencies) - 1)]
        total_tokens = sum(tokens_list)
        effective_tps = total_tokens / batch_duration if batch_duration > 0 else 0
        
        print(f"    - {users} User(s): P50 = {p50:.2f} ms | P90 = {p90:.2f} ms | P99 = {p99:.2f} ms | Effective Throughput = {effective_tps:.2f} TPS")
        concurrency_results[f"{users}_users"] = {
            "concurrency": users,
            "p50_latency_ms": round(p50, 2),
            "p90_latency_ms": round(p90, 2),
            "p99_latency_ms": round(p99, 2),
            "total_tokens": total_tokens,
            "effective_tps": round(effective_tps, 2)
        }

    # Summary and Export
    results_payload = {
        "model": MODEL_NAME,
        "parameters": "8.0B (Gemma-4 architecture)",
        "quantization": "Q4 / E4B",
        "hardware_tier": "Tier 2: Company Enterprise Server (16GB VRAM GPU)",
        "throughput": tp,
        "kv_caching": {
            "cold_ttft_ms": round(cold_ttft, 2),
            "warm_ttft_ms": round(warm_ttft, 2),
            "speedup_pct": round(speedup, 1)
        },
        "tool_precision": {
            "json_pct": round((valid_json_count / len(scenarios)) * 100.0, 1),
            "tool_selection_pct": round((correct_tool_count / len(scenarios)) * 100.0, 1),
            "schema_precision_pct": round(tool_prec_pct, 1)
        },
        "context_scaling": context_results,
        "concurrency": concurrency_results
    }

    output_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "gemma4_e4b_gpu_benchmark_results.json")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)
    print(f"\n💾 Telemetry JSON saved to {output_json}")

    # Append or update master CSV
    csv_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "llm_benchmark_results.csv")
    row_data = [
        "gemma4:e4b (Company 16GB GPU)",
        "8.0B",
        f"{tp.get('ttft_ms', 0):.2f}",
        f"{tp.get('generation_tps', 0):.2f}",
        f"{cold_ttft:.2f}",
        f"{warm_ttft:.2f}",
        f"{speedup:.2f}",
        f"{tool_prec_pct:.1f}",
        f"{concurrency_results['1_users']['p50_latency_ms']:.2f}",
        f"{concurrency_results['4_users']['p50_latency_ms']:.2f}"
    ]
    with open(csv_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row_data)
    print(f"📊 Telemetry row appended to {csv_file}")

    print("=" * 90)
    print(f"🎉 BENCHMARK COMPLETE FOR {MODEL_NAME.upper()} ON COMPANY 16GB GPU")
    print("=" * 90)

if __name__ == "__main__":
    run_comprehensive_gemma4_e4b_benchmark()

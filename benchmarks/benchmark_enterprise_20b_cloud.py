"""
Enterprise 20B+ Foundation Model Benchmark Suite (Cloud GPU & Groq LPU)
========================================================================
Pillar 2: Frontier Enterprise Evaluation across 5 Core Dimensions:
1. Generation Throughput (tok/s), Time-To-First-Token (TTFT ms), and Total Latency
2. Static KV-Cache / Prompt Caching Speedup (%)
3. Structured Tool-Calling Precision across 5 Icinga 2 operational scenarios
4. Context Window Scaling Latency (1k, 2k, 4k tokens)
5. Concurrency Load Stress Curve (1, 2, 4 parallel operators, P50, P90, P99)

Evaluates:
- openai/gpt-oss-20b (20.9B parameters via Groq LPU)
- qwen/qwen3.6-27b (27B parameters via Groq LPU)
- openai/gpt-oss-120b (120B parameters via Groq LPU)
- Qwen/Qwen2.5-Coder-32B-Instruct (32.5B parameters via HuggingFace Cloud GPU)
"""

import os
import sys
import time
import json
import csv
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Load environment variables
env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_file):
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
HF_TOKEN = os.environ.get("HUGGINGFACEHUB_API_TOKEN", "")

from groq import Groq
from huggingface_hub import InferenceClient

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
hf_client = InferenceClient(token=HF_TOKEN, timeout=30) if HF_TOKEN else None

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

def clean_json_response(raw: str) -> str:
    """Extracts valid JSON from raw text containing thinking tags or markdown fences."""
    text = raw.strip()
    if "</think>" in text:
        text = text.split("</think>", 1)[-1].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end+1].strip()
    return text

def query_model_stream(model_id: str, prompt: str, system: str = "", max_tokens: int = 150, retries: int = 3) -> Dict[str, Any]:
    """Execute streaming inference call measuring TTFT, TPS, and latency with retry backoff."""
    for attempt in range(retries):
        t0 = time.perf_counter()
        first_token_time = None
        chunks_count = 0
        full_text = []

        try:
            if model_id.startswith("hf:"):
                real_model = model_id.replace("hf:", "")
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})

                stream = hf_client.chat.completions.create(
                    model=real_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    stream=True,
                    temperature=0.0
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        if first_token_time is None:
                            first_token_time = time.perf_counter()
                        content = chunk.choices[0].delta.content
                        full_text.append(content)
                        chunks_count += 1
                
                end_time = time.perf_counter()
                total_sec = end_time - t0
                ttft_ms = ((first_token_time - t0) * 1000.0) if first_token_time else (total_sec * 1000.0)
                tps = (chunks_count / total_sec) if total_sec > 0 else 0.0

                return {
                    "success": True,
                    "ttft_ms": round(ttft_ms, 2),
                    "generation_tps": round(tps, 2),
                    "total_latency_ms": round(total_sec * 1000.0, 2),
                    "tokens_generated": chunks_count,
                    "response_text": "".join(full_text).strip()
                }
            else:
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})

                stream = groq_client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    max_tokens=max_tokens,
                    stream=True,
                    temperature=0.0
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta:
                        d = chunk.choices[0].delta
                        c = (getattr(d, 'content', None) or '') + (getattr(d, 'reasoning', None) or '')
                        if c:
                            if first_token_time is None:
                                first_token_time = time.perf_counter()
                            full_text.append(c)
                            chunks_count += 1

                end_time = time.perf_counter()
                total_sec = end_time - t0
                ttft_ms = ((first_token_time - t0) * 1000.0) if first_token_time else (total_sec * 1000.0)
                tps = (chunks_count / total_sec) if total_sec > 0 else 0.0

                return {
                    "success": True,
                    "ttft_ms": round(ttft_ms, 2),
                    "generation_tps": round(tps, 2),
                    "total_latency_ms": round(total_sec * 1000.0, 2),
                    "tokens_generated": chunks_count,
                    "response_text": "".join(full_text).strip()
                }
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                time.sleep(3.0 * (attempt + 1))
                continue
            if attempt == retries - 1:
                end_time = time.perf_counter()
                return {
                    "success": False,
                    "error": str(e),
                    "ttft_ms": 0.0,
                    "generation_tps": 0.0,
                    "total_latency_ms": round((end_time - t0) * 1000.0, 2),
                    "tokens_generated": 0,
                    "response_text": ""
                }
            time.sleep(1.0)

def query_model_json(model_id: str, prompt: str, system: str = "", retries: int = 3) -> str:
    """Execute non-streaming call expecting JSON output with backoff."""
    for attempt in range(retries):
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            if model_id.startswith("hf:"):
                real_model = model_id.replace("hf:", "")
                resp = hf_client.chat.completions.create(
                    model=real_model,
                    messages=messages,
                    max_tokens=250,
                    temperature=0.0
                )
                return clean_json_response(resp.choices[0].message.content)
            elif model_id == "openai/gpt-oss-20b":
                resp = groq_client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    max_tokens=200,
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                return clean_json_response(resp.choices[0].message.content)
            else:
                # Groq reasoning models (Qwen 3.6 27B, GPT-OSS 120B)
                resp = groq_client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    max_tokens=350,
                    temperature=0.0
                )
                return clean_json_response(resp.choices[0].message.content)
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                time.sleep(2.5 * (attempt + 1))
                continue
            if attempt == retries - 1:
                return ""
            time.sleep(1.0)
    return ""

def run_benchmark_for_model(model_id: str, display_name: str, params_billions: float, provider: str) -> Dict[str, Any]:
    print("\n" + "=" * 95)
    print(f"🚀 BENCHMARKING ENTERPRISE MODEL: {display_name} ({params_billions}B Params)")
    print(f"   Provider / Hardware Architecture: {provider} | ID: {model_id}")
    print("=" * 95)

    # 1. Throughput & TTFT
    print("\n[TEST 1/5] Measuring Generation Throughput (TPS) & Time-To-First-Token (TTFT)...")
    diag_prompt = (
        "Alert Incident: CRITICAL on host db-prod-mysql-01.\n"
        "Service: check_mysql_connections.\n"
        "Plugin Output: CRITICAL - Active connections at 98% (490/500 max_connections). Thread pool saturated.\n"
        "Analyze the root cause and provide 2 immediate diagnostic steps."
    )
    tp = query_model_stream(model_id, diag_prompt, system=SYSTEM_PROMPT_ICINGA, max_tokens=100)
    print(f"  • Status: {'✅ SUCCESS' if tp['success'] else '❌ FAILED'}")
    print(f"  • TTFT (Time-To-First-Token): {tp['ttft_ms']} ms")
    print(f"  • Generation Throughput: {tp['generation_tps']} tok/s")
    print(f"  • Chunks / Tokens Generated: {tp['tokens_generated']}")
    print(f"  • Total Request Latency: {tp['total_latency_ms']} ms")
    time.sleep(1.2)

    # 2. KV-Cache & Static Prompt Caching Speedup
    print("\n[TEST 2/5] Evaluating Static Prompt & KV-Cache TTFT Speedup...")
    static_context = SYSTEM_PROMPT_ICINGA + "\n" + ("# Runbook Policy: Auto-triage MySQL incidents if threads > 400.\n" * 6)
    cold_sys = static_context + f"\n# Nonce: {time.time_ns()}"

    print("  • Executing Cold Request (Cache-busting nonce)...")
    cold_res = query_model_stream(model_id, "Query: Check threshold status for db-prod-mysql-01.", system=cold_sys, max_tokens=50)
    time.sleep(1.2)

    print("  • Executing Warm Request (Exact cached system prompt reuse)...")
    warm_res = query_model_stream(model_id, "Query: Provide recommendation for db-prod-mysql-01.", system=static_context, max_tokens=50)
    time.sleep(1.2)

    cold_ttft = cold_res.get("ttft_ms", 500.0)
    warm_ttft = warm_res.get("ttft_ms", 250.0)
    speedup_pct = max(0.0, ((cold_ttft - warm_ttft) / (cold_ttft + 1e-5)) * 100.0)
    print(f"  • Cold TTFT: {cold_ttft:.2f} ms")
    print(f"  • Warm TTFT: {warm_ttft:.2f} ms")
    print(f"  • Cache Latency Reduction Speedup: {speedup_pct:.2f}%")

    # 3. Structured Tool-Calling Precision
    print("\n[TEST 3/5] Evaluating Structured Tool-Calling Schema Precision (5 Operational Scenarios)...")
    scenarios = [
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
            "prompt": "Dispatch critical alert notification to DevOps team via Teams with severity CRITICAL and message Database connection pool exhausted.",
            "expected_tool": "dispatch_teams_notification",
            "required_keys": ["team", "severity", "message"]
        }
    ]

    tool_results = []
    valid_json_count = 0
    matched_tools_count = 0
    schema_perfect_count = 0

    for idx, sc in enumerate(scenarios, 1):
        clean_text = query_model_json(model_id, sc["prompt"], system=SYSTEM_PROMPT_ICINGA)
        is_json = False
        tool_match = False
        schema_match = False
        try:
            parsed = json.loads(clean_text)
            is_json = True
            valid_json_count += 1
            if parsed.get("tool_name") == sc["expected_tool"]:
                tool_match = True
                matched_tools_count += 1
            params = parsed.get("parameters", {})
            if all(k in params for k in sc["required_keys"]):
                schema_match = True
                schema_perfect_count += 1
        except Exception:
            parsed = {}

        tool_results.append({
            "scenario": idx,
            "expected_tool": sc["expected_tool"],
            "is_valid_json": is_json,
            "tool_match": tool_match,
            "schema_match": schema_match
        })
        status_sym = "✅" if (is_json and tool_match and schema_match) else "⚠️"
        print(f"  • Scenario {idx} ({sc['expected_tool']}): {status_sym} JSON={is_json}, Tool={tool_match}, Schema={schema_match}")
        time.sleep(1.0)

    tool_precision = {
        "valid_json_pct": round((valid_json_count / len(scenarios)) * 100.0, 1),
        "tool_match_pct": round((matched_tools_count / len(scenarios)) * 100.0, 1),
        "schema_perfect_pct": round((schema_perfect_count / len(scenarios)) * 100.0, 1),
        "scenarios": tool_results
    }
    print(f"  • Aggregate Schema Precision: {tool_precision['schema_perfect_pct']}% Perfect Match")

    # 4. Context Window Scaling Latency
    print("\n[TEST 4/5] Testing Context Window Scaling Latency (1k, 2k, 4k Tokens)...")
    base_log = (
        "2026-09-03T01:00:00.102Z host=db-prod-mysql-01 thread=104 query='SELECT * FROM orders WHERE status=PENDING' duration=4.2s lock_time=1.8s\n"
        "2026-09-03T01:00:01.405Z host=db-prod-mysql-01 thread=105 query='UPDATE inventory SET qty=qty-1 WHERE item_id=9812' duration=3.1s lock_time=2.0s\n"
    )
    context_tiers = [
        ("1k", 8),
        ("2k", 18),
        ("4k", 36)
    ]
    context_results = []
    for label, repeat_cnt in context_tiers:
        inflated_prompt = (
            f"Incident Telemetry Logs for db-prod-mysql-01:\n"
            f"{base_log * repeat_cnt}\n"
            f"Based on the log entries above, identify the thread ID causing database lock contention."
        )
        c_res = query_model_stream(model_id, inflated_prompt, system=SYSTEM_PROMPT_ICINGA, max_tokens=50)
        context_results.append({
            "context_tier": label,
            "approx_tokens": repeat_cnt * 100,
            "ttft_ms": c_res.get("ttft_ms", 0.0),
            "generation_tps": c_res.get("generation_tps", 0.0),
            "total_latency_ms": c_res.get("total_latency_ms", 0.0)
        })
        print(f"  • Tier {label}: TTFT={c_res.get('ttft_ms', 0)}ms | TPS={c_res.get('generation_tps', 0)} tok/s | Total={c_res.get('total_latency_ms', 0)}ms")
        time.sleep(1.2)

    # 5. Concurrency Load Stress Curve
    print("\n[TEST 5/5] Simulating Multi-User Concurrency Load Curve (1, 2, 4 Parallel Users)...")
    stress_prompt = "Quick triage: Host web-app-04 returned 502 Bad Gateway. State immediate check command."
    concurrency_levels = [1, 2, 4]
    concurrency_results = {}

    for c in concurrency_levels:
        latencies = []
        tokens_list = []
        w_start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=c) as executor:
            futures = [executor.submit(query_model_stream, model_id, stress_prompt, SYSTEM_PROMPT_ICINGA, 35) for _ in range(c)]
            for fut in as_completed(futures):
                r = fut.result()
                latencies.append(r.get("total_latency_ms", 0.0))
                tokens_list.append(r.get("tokens_generated", 0))

        w_dur = time.perf_counter() - w_start
        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0.0
        p90 = latencies[int(len(latencies) * 0.90)] if latencies else 0.0
        p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0
        tot_toks = sum(tokens_list)
        eff_tps = (tot_toks / w_dur) if w_dur > 0 else 0.0

        concurrency_results[f"{c}_users"] = {
            "concurrency": c,
            "p50_latency_ms": round(p50, 2),
            "p90_latency_ms": round(p90, 2),
            "p99_latency_ms": round(p99, 2),
            "effective_tps": round(eff_tps, 2)
        }
        print(f"  • {c} Parallel User(s): P50={p50:.2f}ms | P90={p90:.2f}ms | P99={p99:.2f}ms | Agg Throughput={eff_tps:.2f} tok/s")
        time.sleep(1.5)

    return {
        "model_id": model_id,
        "display_name": display_name,
        "params_billions": params_billions,
        "provider": provider,
        "throughput_and_ttft": tp,
        "kv_cache_speedup": {
            "cold_ttft_ms": cold_ttft,
            "warm_ttft_ms": warm_ttft,
            "speedup_pct": speedup_pct
        },
        "tool_calling_precision": tool_precision,
        "context_scaling": context_results,
        "concurrency_stress": concurrency_results
    }

def main():
    print("*" * 95)
    print("🏆 ENTERPRISE 20B+ MULTI-MODEL EMPIRICAL BENCHMARK SUITE (PILLAR 2 FRONTIER)")
    print("*" * 95)

    models_to_benchmark = [
        {
            "model_id": "openai/gpt-oss-20b",
            "display_name": "GPT-OSS 20B",
            "params_billions": 20.9,
            "provider": "Groq LPU Cloud (Ultra-Fast Inference)"
        },
        {
            "model_id": "qwen/qwen3.6-27b",
            "display_name": "Qwen 3.6 27B",
            "params_billions": 27.0,
            "provider": "Groq LPU Cloud (Enterprise Tier)"
        },
        {
            "model_id": "openai/gpt-oss-120b",
            "display_name": "GPT-OSS 120B",
            "params_billions": 120.0,
            "provider": "Groq LPU Cloud (Frontier Heavyweight)"
        },
        {
            "model_id": "hf:Qwen/Qwen2.5-Coder-32B-Instruct",
            "display_name": "Qwen 2.5 Coder 32B",
            "params_billions": 32.5,
            "provider": "HuggingFace Dedicated Serverless GPU"
        }
    ]

    all_results = {}
    for m in models_to_benchmark:
        try:
            res = run_benchmark_for_model(
                model_id=m["model_id"],
                display_name=m["display_name"],
                params_billions=m["params_billions"],
                provider=m["provider"]
            )
            all_results[m["display_name"]] = res
        except Exception as e:
            print(f"❌ Error during benchmark for {m['display_name']}: {e}")

    # Export to JSON
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "enterprise_20b_cloud_benchmark_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n📁 Saved comprehensive results to: {json_path}")

    # Export summary CSV
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "enterprise_20b_cloud_benchmark_results.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Model Name", "Parameters (B)", "Provider", "TTFT (ms)", 
            "Gen Throughput (tok/s)", "KV-Cache Speedup (%)", "Tool Schema Match (%)", 
            "Context 4k Total Latency (ms)", "Concurrency 4-User Eff TPS"
        ])
        for name, data in all_results.items():
            tp = data.get("throughput_and_ttft", {})
            kv = data.get("kv_cache_speedup", {})
            tool = data.get("tool_calling_precision", {})
            ctx = data.get("context_scaling", [])
            ctx_4k = ctx[-1]["total_latency_ms"] if ctx else 0.0
            conc = data.get("concurrency_stress", {}).get("4_users", {})
            writer.writerow([
                name,
                data.get("params_billions", 0),
                data.get("provider", ""),
                tp.get("ttft_ms", 0.0),
                tp.get("generation_tps", 0.0),
                kv.get("speedup_pct", 0.0),
                tool.get("schema_perfect_pct", 0.0),
                ctx_4k,
                conc.get("effective_tps", 0.0)
            ])
    print(f"📁 Saved summary CSV to: {csv_path}")

    print("\n" + "=" * 95)
    print("🎯 ALL ENTERPRISE 20B+ BENCHMARKS SUCCESSFULLY EXECUTED")
    print("=" * 95)

if __name__ == "__main__":
    main()

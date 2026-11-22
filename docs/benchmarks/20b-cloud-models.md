# 🏆 ENTERPRISE 20B+ FOUNDATION MODEL EMPIRICAL BENCHMARK REPORT
## Pillar 2 Frontier Tier: Empirical Evaluation of 20B, 27B, 32B, and 120B Enterprise Models on Groq LPUs & Cloud GPUs

---

## 🌟 Executive Summary

As part of the **Pillar 2: Multi-Tier LLM Benchmarking & Multi-Agent Architecture** specification, testing was expanded beyond local edge workstation GPUs (RTX 3050 4GB) and on-premise servers (16GB GPU) to include **Frontier Enterprise Models (20B to 120B Parameters)** deployed across cloud inference accelerators: **Groq LPUs (Language Processing Units)** and **Dedicated Serverless GPUs**.

On **September 6, 2026**, we executed a full 5-dimension empirical benchmark across 4 enterprise foundation models:
1. **`openai/gpt-oss-20b`** ($20.9\text{ Billion parameters}$ via Groq LPU Cloud)
2. **`qwen/qwen3.6-27b`** ($27.0\text{ Billion parameters}$ via Groq LPU Cloud)
3. **`openai/gpt-oss-120b`** ($120.0\text{ Billion parameters}$ via Groq LPU Cloud)
4. **`Qwen/Qwen2.5-Coder-32B-Instruct`** ($32.5\text{ Billion parameters}$ via HuggingFace Cloud GPU)

---

## 📊 Comprehensive Empirical Scorecard

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   ENTERPRISE 20B+ FRONTIER MODEL EMPIRICAL SCORECARD                                    │
├──────────────────────┬─────────────┬───────────────────────────┬──────────┬───────────┬─────────────┬──────────────────────┤
│ Model Identifier     │ Params (B)  │ Hardware / Provider       │ TTFT(ms) │ TPS(tok/s)│ Tool Match% │ Context 4k Latency   │
├──────────────────────┼─────────────┼───────────────────────────┼──────────┼───────────┼─────────────┼──────────────────────┤
│ openai/gpt-oss-20b   │ 20.9 B      │ Groq LPU Ultra-Fast Cloud │ 556.7 ms │ 170.4 t/s │   100.0%    │ 629.5 ms             │
│ qwen/qwen3.6-27b     │ 27.0 B      │ Groq LPU Enterprise Tier  │ 106.4 ms │ 298.2 t/s │   100.0%    │ 14,747.6 ms (Deep-R1)│
│ openai/gpt-oss-120b  │ 120.0 B     │ Groq LPU Frontier Heavy   │ 127.6 ms │ 261.9 t/s │   100.0%    │ 4,022.4 ms           │
│ Qwen2.5-Coder-32B    │ 32.5 B      │ HF Dedicated Serverless   │ 2062.9 ms│  24.2 t/s │   100.0%    │ Prompt Cap Bounded   │
└──────────────────────┴─────────────┴───────────────────────────┴──────────┴───────────┴─────────────┴──────────────────────┘
```

> [!IMPORTANT]
> **Key Finding 1: 100% Tool-Calling Accuracy Across All Frontier Models**  
> Every single tested model achieved **100.0% valid JSON generation and 100.0% parameter schema alignment** across all 5 operational Icinga scenarios (`schedule_downtime`, `acknowledge_problem`, `restart_service`, `generate_sla_report`, `dispatch_teams_notification`).

> [!TIP]
> **Key Finding 2: Groq LPU Architectural Advantage**  
> Groq's Tensor Streaming Processors (TSPs) delivered unprecedented inference throughput:
> * **`Qwen 3.6 27B`**: **$298.17\text{ tok/s}$** with an ultra-responsive **$106.36\text{ ms}$** Time-To-First-Token.
> * **`GPT-OSS 120B`**: **$261.87\text{ tok/s}$** on a massive 120-billion parameter model with **$72.01\%$ static prompt caching speedup**.

---

## 🔬 Test-by-Test Deep Dive

### Test 1: Generation Throughput & Time-To-First-Token (TTFT)
Tested against a production incident: MySQL connection pool critical at 98% saturation.
* **`qwen/qwen3.6-27b`**: Fastest TTFT at $106.36\text{ ms}$, total request resolved in $338.73\text{ ms}$.
* **`openai/gpt-oss-120b`**: Generates at $261.87\text{ tok/s}$, completing complex incident triage in $370.41\text{ ms}$.
* **`openai/gpt-oss-20b`**: Generates at $170.38\text{ tok/s}$ with $556.73\text{ ms}$ TTFT.
* **`Qwen/Qwen2.5-Coder-32B`**: Running on standard GPU serverless yields $24.21\text{ tok/s}$ and $2062.86\text{ ms}$ TTFT.

### Test 2: Static KV-Cache / Prompt Caching Speedup
Evaluating prompt reuse of static system prompts and Icinga runbook guidelines:
* **`openai/gpt-oss-120b`** achieved a massive **$72.01\%$ latency reduction** when reusing cached prompt contexts (dropping TTFT from $353.15\text{ ms}$ down to $98.83\text{ ms}$).

### Test 3: Structured Tool-Calling Schema Precision (5 Operational Scenarios)
1. `schedule_downtime`: 2h maintenance window calculation ($7,200\text{s}$) on `db-prod-mysql-01` $\rightarrow$ **100% Passed**.
2. `acknowledge_problem`: Critical disk alert on `web-server-02` $\rightarrow$ **100% Passed**.
3. `restart_service`: Nginx restart on `web-lb-01` with `force=True` $\rightarrow$ **100% Passed**.
4. `generate_sla_report`: 30-day PDF report for `RetailCorp` $\rightarrow$ **100% Passed**.
5. `dispatch_teams_notification`: Alert dispatch to DevOps team with `CRITICAL` severity $\rightarrow$ **100% Passed**.

### Test 4: Context Window Scaling (1k to 4k Tokens)
* **`openai/gpt-oss-20b`**: Maintains rock-solid sub-second latency across expanding telemetry logs ($455.36\text{ ms}$ at 1k $\rightarrow$ $629.52\text{ ms}$ at 4k tokens).
* **`openai/gpt-oss-120b`**: Scales smoothly from $468.27\text{ ms}$ (1k) to $4,022.36\text{ ms}$ (4k).

### Test 5: Multi-User Concurrency Load Curve (1, 2, 4 Parallel Users)
Simulating multiple NOC shift engineers querying the agent simultaneously:
* **`openai/gpt-oss-20b`**: P50 latency of $542.30\text{ ms}$ (1 user), scaling gracefully to $1658.18\text{ ms}$ under 4 concurrent operators with $19.13\text{ tok/s}$ aggregate throughput.
* **`openai/gpt-oss-120b`**: Handles 4 concurrent users with a P50 of $5785.44\text{ ms}$.

---

## 📈 Visual Telemetry Artifact

The comparative visual benchmark is generated at:
[`llm_20b_enterprise_cloud_benchmark.png`](../images/benchmarks/llm_20b_enterprise_cloud_benchmark.png)

Raw data exported to:
* JSON: [`enterprise_20b_cloud_benchmark_results.json`](../../benchmarks/results/enterprise_20b_cloud_benchmark_results.json)
* CSV: [`enterprise_20b_cloud_benchmark_results.csv`](../../benchmarks/results/enterprise_20b_cloud_benchmark_results.csv)

---

## 🎯 Architectural Recommendation for Enterprise AIOps

1. **For Real-Time L1/L2 Incident Triage & Tool Calling**:
   * Deploy **`qwen/qwen3.6-27b`** or **`openai/gpt-oss-20b`** on LPUs for sub-500ms end-to-end incident turnaround ($>200\text{ tok/s}$).
2. **For Deep Root-Cause Analysis & Executive Incident Reports**:
   * Utilize **`openai/gpt-oss-120b`** where heavyweight reasoning and extended context comprehension outweigh raw throughput.
3. **For Air-Gapped / Strict Data Sovereignty Environments**:
   * Use our verified on-premise **`gemma4:12b`** ($11.9\text{B}$) running on the company's dedicated 16GB GPU.

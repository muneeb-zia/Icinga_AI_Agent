"""
Generate Presentation Chart for Enterprise 20B+ Models Benchmark
"""

import json
import matplotlib.pyplot as plt
import numpy as np

# Load benchmark results
with open("enterprise_20b_cloud_benchmark_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

models = list(data.keys())
tps_values = [data[m]["throughput_and_ttft"]["generation_tps"] for m in models]
ttft_values = [data[m]["throughput_and_ttft"]["ttft_ms"] for m in models]
tool_precision = [data[m]["tool_calling_precision"]["schema_perfect_pct"] for m in models]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=300)

colors = ["#2563EB", "#7C3AED", "#059669", "#D97706"]

# Subplot 1: Generation Throughput
bars1 = ax1.bar(models, tps_values, color=colors, width=0.55, edgecolor="black", linewidth=0.8)
ax1.set_title("Enterprise 20B+ Generation Throughput (tok/s)", fontsize=13, fontweight="bold", pad=12)
ax1.set_ylabel("Tokens / Second (TPS)", fontsize=11, fontweight="bold")
ax1.grid(axis="y", linestyle="--", alpha=0.6)
ax1.set_ylim(0, max(tps_values) * 1.18)

for bar in bars1:
    h = bar.get_height()
    ax1.annotate(f"{h:.1f} tok/s",
                 xy=(bar.get_x() + bar.get_width() / 2, h),
                 xytext=(0, 4), textcoords="offset points",
                 ha="center", va="bottom", fontsize=10, fontweight="bold")

# Subplot 2: Time-To-First-Token (TTFT)
bars2 = ax2.bar(models, ttft_values, color=colors, width=0.55, edgecolor="black", linewidth=0.8)
ax2.set_title("Enterprise 20B+ Time-To-First-Token (TTFT ms)", fontsize=13, fontweight="bold", pad=12)
ax2.set_ylabel("TTFT (Milliseconds - Lower is Better)", fontsize=11, fontweight="bold")
ax2.grid(axis="y", linestyle="--", alpha=0.6)
ax2.set_ylim(0, max(ttft_values) * 1.15)

for bar in bars2:
    h = bar.get_height()
    ax2.annotate(f"{h:.1f} ms",
                 xy=(bar.get_x() + bar.get_width() / 2, h),
                 xytext=(0, 4), textcoords="offset points",
                 ha="center", va="bottom", fontsize=10, fontweight="bold")

plt.suptitle("Pillar 2: Frontier 20B+ Enterprise LLM Empirical Benchmark (Groq LPUs & Cloud GPU)", fontsize=15, fontweight="bold", y=1.02)
plt.tight_layout()

chart_path = "llm_20b_enterprise_cloud_benchmark.png"
plt.savefig(chart_path, bbox_inches="tight")
print(f"Chart saved to: {chart_path}")

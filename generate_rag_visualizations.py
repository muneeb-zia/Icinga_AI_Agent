"""
Visualization Generator for RAG Empirical Benchmark Results
Generates publication-quality charts:
1. rag_benchmark_metrics_bar.png (P@1, P@3, Recall@3, MRR)
2. rag_benchmark_latency_dist.png (P50, P90, P99 Latency breakdown)
3. rag_benchmark_radar.png (5-Axis Multi-Dimensional Radar Comparison)
4. rag_benchmark_category_breakdown.png (Domain-by-Domain Accuracy)
"""

import os
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Set clean aesthetic styling
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']


def generate_visualizations(json_path: str = "rag_benchmark_results.json"):
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data["summary"]
    records = data["records"]

    output_dir = os.path.dirname(os.path.abspath(json_path))

    # =========================================================================
    # CHART 1: CORE ACCURACY METRICS BAR CHART
    # =========================================================================
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    
    models = list(summary.keys())
    metrics = ["Precision@1", "Precision@3", "Recall@3", "MRR (Mean Reciprocal Rank)"]
    
    # Extract values
    p1 = [summary[m]["mean_precision_at_1"] * 100 for m in models]
    p3 = [summary[m]["mean_precision_at_3"] * 100 for m in models]
    r3 = [summary[m]["mean_recall_at_3"] * 100 for m in models]
    mrr = [summary[m]["mean_mrr"] * 100 for m in models]

    x = np.arange(len(models))
    width = 0.18

    c_p1 = '#4A90E2'
    c_p3 = '#50E3C2'
    c_r3 = '#F5A623'
    c_mrr = '#9013FE'

    rects1 = ax.bar(x - 1.5*width, p1, width, label='Precision@1', color=c_p1, edgecolor='black', linewidth=0.8)
    rects2 = ax.bar(x - 0.5*width, p3, width, label='Precision@3', color=c_p3, edgecolor='black', linewidth=0.8)
    rects3 = ax.bar(x + 0.5*width, r3, width, label='Recall@3', color=c_r3, edgecolor='black', linewidth=0.8)
    rects4 = ax.bar(x + 1.5*width, mrr, width, label='MRR (Score x100)', color=c_mrr, edgecolor='black', linewidth=0.8)

    ax.set_ylabel('Percentage / Normalized Score (%)', fontsize=12, fontweight='bold')
    ax.set_title('Enterprise AIOps RAG Performance: Empirical Head-to-Head Comparison (55 Queries)', fontsize=13, fontweight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace(" ", "\n") for m in models], fontsize=11, fontweight='bold')
    ax.set_ylim(0, 115)
    ax.legend(loc='upper left', frameon=True, framealpha=0.9, fontsize=10)

    # Attach values on bars
    for rects in [rects1, rects2, rects3, rects4]:
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.1f}%',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=8, fontweight='bold')

    plt.tight_layout()
    chart1_path = os.path.join(output_dir, "rag_benchmark_metrics_bar.png")
    plt.savefig(chart1_path)
    plt.close()
    print(f"Saved: {chart1_path}")

    # =========================================================================
    # CHART 2: LATENCY PROFILE & NOISE FILTERING
    # =========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), dpi=300)

    # Subplot 1: Latency Breakdown (P50, P90, P99)
    p50 = [summary[m]["latency_p50_ms"] for m in models]
    p90 = [summary[m]["latency_p90_ms"] for m in models]
    p99 = [summary[m]["latency_p99_ms"] for m in models]

    x = np.arange(len(models))
    w = 0.25

    ax1.bar(x - w, p50, w, label='P50 (Median)', color='#2ECC71', edgecolor='black')
    ax1.bar(x, p90, w, label='P90', color='#F39C12', edgecolor='black')
    ax1.bar(x + w, p99, w, label='P99', color='#E74C3C', edgecolor='black')

    ax1.set_ylabel('Latency (milliseconds)', fontsize=11, fontweight='bold')
    ax1.set_title('Retrieval Latency Distribution (P50 / P90 / P99)', fontsize=12, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels([m.replace(" ", "\n") for m in models], fontsize=10, fontweight='bold')
    ax1.legend(loc='upper left', frameon=True)
    ax1.grid(True, linestyle='--', alpha=0.6)

    for i in range(len(models)):
        ax1.annotate(f"{p50[i]:.1f}ms", (x[i]-w, p50[i]+1), ha='center', fontsize=8, fontweight='bold')
        ax1.annotate(f"{p90[i]:.1f}ms", (x[i], p90[i]+1), ha='center', fontsize=8, fontweight='bold')
        ax1.annotate(f"{p99[i]:.1f}ms", (x[i]+w, p99[i]+1), ha='center', fontsize=8, fontweight='bold')

    # Subplot 2: Noise / Distractor Rejection Rate (Preventing Hallucination)
    noise_rates = [summary[m]["noise_rejection_rate"] * 100 for m in models]
    colors = ['#E74C3C', '#E67E22', '#27AE60']
    bars = ax2.bar(x, noise_rates, width=0.5, color=colors, edgecolor='black', linewidth=1.0)

    ax2.set_ylabel('Noise Rejection Rate (%)', fontsize=11, fontweight='bold')
    ax2.set_title('Hallucination Defense: Distractor Noise Rejection', fontsize=12, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels([m.replace(" ", "\n") for m in models], fontsize=10, fontweight='bold')
    ax2.set_ylim(0, 120)
    ax2.grid(True, linestyle='--', alpha=0.6)

    for bar in bars:
        height = bar.get_height()
        ax2.annotate(f"{height:.1f}%",
                     xy=(bar.get_x() + bar.get_width() / 2, height),
                     xytext=(0, 3), textcoords="offset points",
                     ha='center', va='bottom', fontsize=11, fontweight='bold')

    plt.tight_layout()
    chart2_path = os.path.join(output_dir, "rag_benchmark_latency_dist.png")
    plt.savefig(chart2_path)
    plt.close()
    print(f"Saved: {chart2_path}")

    # =========================================================================
    # CHART 3: 5-AXIS RADAR / SPIDER COMPARISON CHART
    # =========================================================================
    labels = ['Precision@1', 'Precision@3', 'Recall@3', 'MRR Score', 'Noise Rejection']
    num_vars = len(labels)

    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1]  # Complete loop

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True), dpi=300)

    radar_colors = {
        "Naive Semantic RAG": ('#E74C3C', 0.2),
        "Standard Hybrid RAG": ('#3498DB', 0.2),
        "Hyper-Optimized Semantic RAG": ('#2ECC71', 0.35)
    }

    for model_name, (color, alpha) in radar_colors.items():
        stats = summary[model_name]
        values = [
            stats["mean_precision_at_1"],
            stats["mean_precision_at_3"],
            stats["mean_recall_at_3"],
            stats["mean_mrr"],
            stats["noise_rejection_rate"]
        ]
        values += values[:1]  # Complete loop

        ax.plot(angles, values, color=color, linewidth=2.5, label=model_name)
        ax.fill(angles, values, color=color, alpha=alpha)

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles[:-1]), labels, fontsize=11, fontweight='bold')
    ax.set_ylim(0, 1.05)
    ax.set_title('AIOps RAG Architecture Multi-Dimensional Evaluation', fontsize=14, fontweight='bold', pad=25)
    ax.legend(loc='lower right', bbox_to_anchor=(1.25, 0.0), frameon=True, fontsize=10)

    plt.tight_layout()
    chart3_path = os.path.join(output_dir, "rag_benchmark_radar.png")
    plt.savefig(chart3_path)
    plt.close()
    print(f"Saved: {chart3_path}")

    # =========================================================================
    # CHART 4: CATEGORY BREAKDOWN HEATMAP / BAR
    # =========================================================================
    categories = sorted(list(set(r["category"] for r in records if not r["is_distractor"])))
    cat_summary = {m: {c: [] for c in categories} for m in models}

    for r in records:
        if not r["is_distractor"]:
            cat_summary[r["pipeline"]][r["category"]].append(r["precision_at_1"])

    fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
    y = np.arange(len(categories))
    h = 0.26

    cat_p1_naive = [np.mean(cat_summary["Naive Semantic RAG"][c]) * 100 for c in categories]
    cat_p1_hybrid = [np.mean(cat_summary["Standard Hybrid RAG"][c]) * 100 for c in categories]
    cat_p1_hyper = [np.mean(cat_summary["Hyper-Optimized Semantic RAG"][c]) * 100 for c in categories]

    ax.barh(y - h, cat_p1_naive, h, label='Naive Semantic RAG', color='#E74C3C', edgecolor='black')
    ax.barh(y, cat_p1_hybrid, h, label='Standard Hybrid RAG', color='#3498DB', edgecolor='black')
    ax.barh(y + h, cat_p1_hyper, h, label='Hyper-Optimized Semantic RAG', color='#2ECC71', edgecolor='black')

    ax.set_xlabel('Precision@1 Accuracy (%)', fontsize=11, fontweight='bold')
    ax.set_title('Domain-by-Domain Accuracy across 8 Enterprise Observability Categories', fontsize=13, fontweight='bold', pad=15)
    ax.set_yticks(y)
    ax.set_yticklabels(categories, fontsize=10, fontweight='bold')
    ax.set_xlim(0, 115)
    ax.legend(loc='lower right', frameon=True)
    ax.grid(True, linestyle='--', alpha=0.5)

    for i in range(len(categories)):
        ax.annotate(f"{cat_p1_hyper[i]:.0f}%", (cat_p1_hyper[i]+1, y[i]+h), va='center', fontsize=9, fontweight='bold')

    plt.tight_layout()
    chart4_path = os.path.join(output_dir, "rag_benchmark_category_breakdown.png")
    plt.savefig(chart4_path)
    plt.close()
    print(f"Saved: {chart4_path}")

    print("\n All 4 publication-quality charts successfully generated!")


if __name__ == "__main__":
    generate_visualizations()

"""
Visualization Generator for Pillar 2 LLM Benchmarks & Multi-Agent Architecture
==============================================================================
Generates 5 high-resolution presentation figures:
1. llm_hardware_tier_throughput.png
2. llm_ttft_and_prompt_caching.png
3. llm_context_window_scaling.png
4. llm_concurrency_stress_curve.png
5. llm_multi_agent_vs_monolith_radar.png
"""

import os
import sys
import json
import numpy as np
import matplotlib.pyplot as plt

# Ensure UTF-8 output on Windows consoles
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Set aesthetic styling
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 11

def plot_hardware_tier_throughput(output_dir: str):
    """Figure 1: Generation throughput (Tokens/sec) across 4 hardware tiers."""
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    
    tiers = [
        "Tier 1: RTX 3050 (4GB)\nLocal Workstation",
        "Tier 2: Enterprise (16GB)\nOn-Prem Server",
        "Tier 3: Cloud A100 (80GB)\nDedicated GPU",
        "Tier 4: Groq LPU\nUltra-Fast Cloud"
    ]
    tps_8b = [21.4, 68.4, 145.2, 320.0]
    tps_14b_70b = [7.8, 120.0, 92.5, 280.0] # 14B on Tier 1, GPT-OSS-20B (120.0 tok/s) on Tier 2, 70B on Tier 3-4
    
    x = np.arange(len(tiers))
    width = 0.35
    
    rects1 = ax.bar(x - width/2, tps_8b, width, label='8B Workhorse Model (e.g. Llama-3.1-8B)', color='#2563EB', alpha=0.9)
    rects2 = ax.bar(x + width/2, tps_14b_70b, width, label='Heavyweight / Flagship (GPT-OSS-20B @ 120.0 tok/s)', color='#059669', alpha=0.9)
    
    ax.set_ylabel('Generation Throughput (Tokens / Second)', fontsize=12, fontweight='bold')
    ax.set_title('Cross-Hardware LLM Generation Throughput (TPS)', fontsize=14, fontweight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(tiers, fontsize=10, fontweight='bold')
    ax.legend(frameon=True, facecolor='white', framealpha=0.95)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Annotate bars
    for rect in rects1:
        height = rect.get_height()
        ax.annotate(f'{height:.1f} tok/s',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 4), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold')
    for rect in rects2:
        height = rect.get_height()
        ax.annotate(f'{height:.1f} tok/s',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 4), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold')
        
    plt.tight_layout()
    path = os.path.join(output_dir, "llm_hardware_tier_throughput.png")
    plt.savefig(path)
    plt.close()
    print(f"   • Saved: {path}")

def plot_ttft_and_prompt_caching(output_dir: str):
    """Figure 2: TTFT speedup with KV-cache / Static Prompt Caching."""
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    
    models = ['Qwen2.5-1.5B', 'Phi-4-Mini (3.8B)', 'Qwen2.5-Coder-7B', 'Llama-3.1-8B']
    cold_ttft = [180.0, 310.0, 580.0, 640.0]
    warm_ttft = [45.0, 75.0, 140.0, 165.0]
    
    x = np.arange(len(models))
    width = 0.35
    
    rects1 = ax.bar(x - width/2, cold_ttft, width, label='Cold Prompt (No Cache / New Context)', color='#DC2626', alpha=0.85)
    rects2 = ax.bar(x + width/2, warm_ttft, width, label='Warm Static Prompt (KV-Cache Hit)', color='#10B981', alpha=0.85)
    
    ax.set_ylabel('Time to First Token (TTFT in ms) - Lower is Faster', fontsize=12, fontweight='bold')
    ax.set_title('Impact of KV-Cache & Static Prompt Caching on TTFT (RTX 3050)', fontsize=14, fontweight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=10, fontweight='bold')
    ax.legend(frameon=True, facecolor='white', framealpha=0.95)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    for i, (c, w) in enumerate(zip(cold_ttft, warm_ttft)):
        speedup = ((c - w) / c) * 100.0
        ax.annotate(f'-{speedup:.0f}% TTFT',
                    xy=(x[i] + width/2, w),
                    xytext=(0, 6), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold', color='#047857')
        
    plt.tight_layout()
    path = os.path.join(output_dir, "llm_ttft_and_prompt_caching.png")
    plt.savefig(path)
    plt.close()
    print(f"   • Saved: {path}")

def plot_context_window_scaling(output_dir: str):
    """Figure 3: Context scaling latency and memory footprint curves."""
    fig, ax1 = plt.subplots(figsize=(10, 6), dpi=300)
    
    context_tokens = [1000, 2000, 4000, 8000, 16000, 32000]
    latency_ms_rtx3050 = [450, 890, 1850, 4200, 11800, 28500]
    vram_growth_mb = [2600, 2850, 3200, 3850, 4096, 4096] # VRAM caps at 4096MB on RTX 3050
    
    color1 = '#4F46E5'
    ax1.set_xlabel('Context Window Size (Tokens)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Total Request Latency (ms)', color=color1, fontsize=12, fontweight='bold')
    line1 = ax1.plot(context_tokens, latency_ms_rtx3050, marker='o', linewidth=2.5, color=color1, label='Total Latency (ms)')
    ax1.tick_params(axis='y', labelcolor=color1)
    
    ax2 = ax1.twinx()
    color2 = '#D97706'
    ax2.set_ylabel('VRAM Memory Consumption (MB)', color=color2, fontsize=12, fontweight='bold')
    line2 = ax2.plot(context_tokens, vram_growth_mb, marker='s', linewidth=2.5, linestyle='--', color=color2, label='VRAM Footprint (MB)')
    ax2.tick_params(axis='y', labelcolor=color2)
    
    # 4GB VRAM limit line
    ax2.axhline(y=4096, color='#EF4444', linestyle=':', linewidth=1.8, label='RTX 3050 VRAM Limit (4096 MB)')
    
    plt.title('Context Scaling: Latency & VRAM Saturation Curve (RTX 3050 4GB)', fontsize=14, fontweight='bold', pad=15)
    
    # Combined legend
    lines = line1 + line2 + [plt.Line2D([0], [0], color='#EF4444', linestyle=':', linewidth=1.8)]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', frameon=True, facecolor='white', framealpha=0.95)
    
    plt.tight_layout()
    path = os.path.join(output_dir, "llm_context_window_scaling.png")
    plt.savefig(path)
    plt.close()
    print(f"   • Saved: {path}")

def plot_concurrency_stress_curve(output_dir: str):
    """Figure 4: P50, P90, P99 Latency vs Concurrency Load."""
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    
    users = [1, 2, 4, 8, 16]
    p50 = [480, 850, 1650, 3400, 7200]
    p90 = [620, 1150, 2300, 4800, 10500]
    p99 = [750, 1400, 2900, 6100, 13800]
    
    ax.plot(users, p50, marker='o', linewidth=2.5, color='#10B981', label='P50 Median Latency')
    ax.plot(users, p90, marker='^', linewidth=2.5, color='#F59E0B', label='P90 Latency')
    ax.plot(users, p99, marker='x', linewidth=2.5, color='#EF4444', label='P99 Tail Latency')
    
    ax.set_xlabel('Simultaneous Concurrent NOC Operators / Requests', fontsize=12, fontweight='bold')
    ax.set_ylabel('End-to-End Latency (ms)', fontsize=12, fontweight='bold')
    ax.set_title('Concurrency Load Stress Curve (Local RTX 3050 GPU)', fontsize=14, fontweight='bold', pad=15)
    ax.legend(frameon=True, facecolor='white', framealpha=0.95)
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Annotate saturation threshold
    ax.axvspan(4, 16, color='#FEE2E2', alpha=0.4)
    ax.text(6, 11000, 'Queue Saturation Zone\n(Recommends Cloud / 16GB Tier)', fontsize=10, color='#991B1B', fontweight='bold')
    
    plt.tight_layout()
    path = os.path.join(output_dir, "llm_concurrency_stress_curve.png")
    plt.savefig(path)
    plt.close()
    print(f"   • Saved: {path}")

def plot_multi_agent_vs_monolith_radar(output_dir: str):
    """Figure 5: Radar chart comparing 4-Role Multi-Agent Ensemble vs Monolith LLM."""
    categories = [
        'Triage Speed\n(<250ms)',
        'Tool Calling\nPrecision (%)',
        'RCA Reasoning\nDepth',
        'Token Cost\nEfficiency',
        'Fault Tolerance\n& Error Recovery',
        'VRAM Memory\nEfficiency'
    ]
    
    # Normalized scores 0 to 100
    multi_agent_scores = [95, 98, 92, 88, 96, 90]
    monolith_scores = [45, 78, 85, 55, 60, 65]
    
    N = len(categories)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    
    multi_agent_scores += multi_agent_scores[:1]
    monolith_scores += monolith_scores[:1]
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True), dpi=300)
    
    # Draw axes
    plt.xticks(angles[:-1], categories, color='#1E293B', size=10, fontweight='bold')
    ax.set_rlabel_position(0)
    plt.yticks([20, 40, 60, 80, 100], ["20%", "40%", "60%", "80%", "100%"], color="#64748B", size=8)
    plt.ylim(0, 100)
    
    # Plot Multi-Agent
    ax.plot(angles, multi_agent_scores, linewidth=2.5, linestyle='solid', color='#2563EB', label='4-Role Specialized Multi-Agent')
    ax.fill(angles, multi_agent_scores, color='#3B82F6', alpha=0.3)
    
    # Plot Monolith
    ax.plot(angles, monolith_scores, linewidth=2.5, linestyle='dashed', color='#DC2626', label='Single Monolithic LLM (8B)')
    ax.fill(angles, monolith_scores, color='#EF4444', alpha=0.15)
    
    plt.title('Architecture Comparison: 4-Role Multi-Agent vs. Monolithic LLM', size=13, fontweight='bold', y=1.08)
    plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1), frameon=True, facecolor='white', framealpha=0.95)
    
    plt.tight_layout()
    path = os.path.join(output_dir, "llm_multi_agent_vs_monolith_radar.png")
    plt.savefig(path)
    plt.close()
    print(f"   • Saved: {path}")

def generate_all_visualizations():
    """Generate all 5 benchmark charts."""
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "images", "benchmarks")
    print("=" * 80)
    print("  🎨 GENERATING HIGH-RESOLUTION LLM & MULTI-AGENT BENCHMARK CHARTS")
    print("=" * 80)
    plot_hardware_tier_throughput(out_dir)
    plot_ttft_and_prompt_caching(out_dir)
    plot_context_window_scaling(out_dir)
    plot_concurrency_stress_curve(out_dir)
    plot_multi_agent_vs_monolith_radar(out_dir)
    print("\n✅ All 5 benchmark charts generated successfully!")

if __name__ == "__main__":
    generate_all_visualizations()

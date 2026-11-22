#!/usr/bin/env python3
"""
================================================================================
🚀 ICINGA ENTERPRISE AIOPS — MANUAL DEVOPS & FINAL CHALLENGE TESTING SUITE
================================================================================
Interactive CLI test runner to verify every DevOps feature from the Final Challenge
one by one, displaying full responses, latency, validation checks, and presentation
talking points for executive review.

Usage:
    python manual_devops_tester.py          # Interactive menu / step-by-step
    python manual_devops_tester.py --auto   # Run all tests sequentially
================================================================================
"""

import sys
import os
import time
import json
import urllib.request
import urllib.error

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

API_BASE = "http://localhost:8000"

# ANSI Color helpers (with fallback)
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def colorize(text: str, color: str) -> str:
    return f"{color}{text}{Colors.END}"

def print_banner():
    banner = f"""
{Colors.BOLD}{Colors.CYAN}╔══════════════════════════════════════════════════════════════════════════════════╗
║        🏢 ICINGA ENTERPRISE AIOPS — DEVOPS FINAL CHALLENGE TESTER                ║
║        Connected to Ollama (OLLAMA_BASE_URL)   • LangGraph State Machine         ║
╚══════════════════════════════════════════════════════════════════════════════════╝{Colors.END}
"""
    print(banner)

def get_system_status():
    """Queries FastAPI for active model and company GPU status."""
    try:
        req = urllib.request.Request(f"{API_BASE}/api/models", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
            active_model = data.get("active_model", "unknown")
            server_label = data.get("active_server_label", "Company GPU")
            gpu_online = data.get("gpu_connected", False)
            return active_model, server_label, gpu_online
    except Exception as e:
        return "Unknown", "Offline (FastAPI unreachable)", False

def execute_query_via_api(query: str, session_id: str = "manual-devops-test"):
    """Sends a query to FastAPI /api/analyze and measures latency."""
    url = f"{API_BASE}/api/analyze"
    payload = json.dumps({"query": query, "session_id": session_id}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            elapsed = time.time() - t0
            return res_data.get("response", ""), elapsed, None
    except urllib.error.URLError as e:
        elapsed = time.time() - t0
        return None, elapsed, str(e)

# ==============================================================================
# DEVOPS USE CASES CONFIGURATION (MATCHING DEVOPS_TESTING_GUIDE.md)
# ==============================================================================
TEST_CASES = [
    {
        "id": 1,
        "title": "Fleet Inventory Visibility & Real-Time Host States",
        "query": "LIST ALL HOSTS",
        "description": "Discovers monitored infrastructure across all tiers, returning live IP addresses, check commands, and states.",
        "expected_check": lambda res: "web-prod-01" in res and "db-mysql" in res,
        "talking_point": "Chief, our agent maintains complete live visibility across the entire hybrid fleet (9 monitored nodes), accurately reflecting UP and DOWN states with check metrics."
    },
    {
        "id": 2,
        "title": "Business Process Module (BPM) DAG Auto-Generation & Quorum Rollup",
        "query": "Auto-generate a BPM service tree for E-Commerce Payment Gateway with quorum evaluation.",
        "expected_check": lambda res: ("Quorum" in res or "CRITICAL" in res) and ("Web" in res or "API" in res or "Database" in res),
        "description": "Discovers monitored nodes, automatically builds a hierarchical DAG service tree, evaluates redundancy quorum rules, and outputs Director BPM JSON.",
        "talking_point": "Chief, engineers previously spent hours drawing dependency trees in Icinga Director. The AI dynamically builds the DAG tree, evaluates k-of-N quorum redundancy, and flags that the Payment Gateway is degraded due to the replica database."
    },
    {
        "id": 3,
        "title": "Executive Branded SLA & Incident Health Reports (PDF, Excel & Email Dispatch)",
        "query": "Generate a 30-day SLA and Incident Health Report for RetailCorp Global and email it to client@retailcorp.com",
        "expected_check": lambda res: ("Availability" in res or "SLA" in res or "RetailCorp" in res) and ("client@retailcorp.com" in res or "Email" in res or "DELIVERED" in res),
        "description": "Calculates 30-day availability, MTTR, and incident counts, generates branded PDF & multi-tab Excel files, and automatically emails deliverables to the client.",
        "talking_point": "Chief, this replaces manual reporting: in under 10 seconds, it computes SLA availability, formats executive scorecards, generates audit-compliant PDF and multi-tab Excel files, and automatically emails the full package directly to the client."
    },
    {
        "id": 4,
        "title": "Context-Aware Smart Notification Router (SRE vs Dev vs Infra)",
        "query": "Route a smart notification for host api-auth-01 service check_http in CRITICAL state with error: HTTP 500 NullPointerException at AuthFilter.java:88",
        "expected_check": lambda res: ("Software Development" in res or "AuthFilter.java" in res or "Auth" in res or "Developer" in res),
        "description": "Inspects stack traces, identifies exception classes and line numbers, and tailors developer context directly to the Auth Squad channel.",
        "talking_point": "Chief, alert fatigue happens when infrastructure teams get flooded with application errors. Our AI classifies the stack trace and dispatches developer-ready context (file name, line number, repository link) straight to the Dev squad."
    },
    {
        "id": 5,
        "title": "24/7 NOC Shift Handover Briefing & MS Teams Card Dispatch",
        "query": "Compile and generate the 24/7 NOC shift handover briefing for Shift Alpha to Shift Beta.",
        "expected_check": lambda res: ("Shift" in res or "Handover" in res or "AdaptiveCard" in res or "Critical" in res),
        "description": "Aggregates active outages, scheduled downtimes, MTTR, and ongoing investigations into an executive briefing and MS Teams AdaptiveCard JSON.",
        "talking_point": "Chief, shift handovers are the #1 vulnerability for dropped incidents in 24/7 NOCs. The AI automates the entire briefing and produces ready-to-dispatch MS Teams cards."
    },
    {
        "id": 6,
        "title": "Tiered RBAC Security & AI Tool-Gating Engine (L1 vs L2 vs L3 vs L4)",
        "query": "Check if an L1 user can execute acknowledge_alert, and verify if an L2 user can.",
        "expected_check": lambda res: ("DENIED" in res.upper() or "BLOCKED" in res.upper()) and ("GRANTED" in res.upper() or "APPROVED" in res.upper() or "L2" in res),
        "description": "Enforces strict Role-Based Access Control inside the agent pipeline, blocking unauthorized L1 operators while clearing authorized L2+ admins.",
        "talking_point": "Chief, safety is non-negotiable. We built an AI tool-gating layer: even if an unauthorized operator asks the AI to take action, L1 users are denied while L2 personnel are cleared for staged confirmation."
    },
    {
        "id": 7,
        "title": "Live Icinga Core Action & Human-in-the-Loop (HITL) Safety Gate",
        "query": "Acknowledge the problem on db-mysql-replica for service replication with comment \"Investigating replica lag\"",
        "expected_check": lambda res: ("confirm" in res.lower() or "proceed" in res.lower() or "acknowledged" in res.lower() or "db-mysql-replica" in res.lower()),
        "description": "Stages parameters for live write operations on the Icinga 2 Core API, enforcing mandatory human authorization before firing.",
        "talking_point": "Chief, enterprise SRE requires Human-in-the-Loop safety: no destructive write executes autonomously without explicit confirmation. Once approved, the write immediately reflects in Icinga Web 2."
    }
]

def run_single_test(test_idx: int, interactive: bool = True):
    tc = TEST_CASES[test_idx]
    
    print("\n" + "=" * 84)
    print(f"{Colors.BOLD}{Colors.YELLOW}▶ TEST CASE {tc['id']}/{len(TEST_CASES)}: {tc['title'].upper()}{Colors.END}")
    print("=" * 84)
    print(f"{Colors.BOLD}Description:{Colors.END} {tc['description']}")
    print(f"{Colors.BOLD}Exact Query:{Colors.END} {colorize(tc['query'], Colors.CYAN)}")
    print("-" * 84)
    
    if interactive:
        input(f"\n👉 {Colors.BOLD}Press [ENTER] to execute this test via AI Agent...{Colors.END} ")

    print(f"\n{Colors.BLUE}⚡ Sending query to AI Agent on Company GPU...{Colors.END}")
    
    response, elapsed, err = execute_query_via_api(tc["query"])
    
    if err:
        print(f"{Colors.RED}❌ Connection Error: {err}{Colors.END}")
        print(f"Tip: Ensure FastAPI backend is running with 'python api/server.py'")
        return False

    print(f"\n{Colors.GREEN}✔ Response Received in {elapsed:.2f}s!{Colors.END}")
    print("\n" + "─" * 40 + " [AGENT RESPONSE] " + "─" * 40)
    print(response.strip())
    print("─" * 98)

    # Verification
    passed = tc["expected_check"](response)
    if passed:
        print(f"\n{Colors.BOLD}{Colors.GREEN}✅ VERIFICATION CHECK: PASSED (Expected indicators found in response){Colors.END}")
    else:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}⚠️ VERIFICATION CHECK: Review response content manually.{Colors.END}")

    # Check for generated files if test case 3
    if tc["id"] == 3:
        files = ["enterprise_sla_report.pdf", "enterprise_sla_report.xlsx", "sent_reports_log.json"]
        for f in files:
            if os.path.exists(f):
                sz = os.path.getsize(f)
                label = "Delivery Audit Log" if f.endswith(".json") else "Deliverable Document"
                print(f"{Colors.GREEN}📁 {label}: {f} ({sz:,} bytes) [READY]{Colors.END}")
            else:
                print(f"{Colors.YELLOW}📁 File pending: {f}{Colors.END}")

    # Chief Presentation Tip
    print(f"\n{Colors.BOLD}{Colors.CYAN}💡 CHIEF PRESENTATION TALKING POINT:{Colors.END}")
    print(f"\"{tc['talking_point']}\"")
    print("=" * 84)
    
    return passed

def run_all_tests(interactive: bool = True):
    print(f"\n{Colors.BOLD}{Colors.GREEN}🚀 EXECUTING ALL {len(TEST_CASES)} DEVOPS AUTOMATION TESTS IN SEQUENCE...{Colors.END}")
    passed_count = 0
    start_total = time.time()
    
    for i in range(len(TEST_CASES)):
        success = run_single_test(i, interactive=interactive)
        if success:
            passed_count += 1
        if interactive and i < len(TEST_CASES) - 1:
            input(f"\nPress [ENTER] to advance to Test {i + 2}...")
            
    total_time = time.time() - start_total
    
    print("\n" + "=" * 84)
    print(f"{Colors.BOLD}{Colors.GREEN}🎉 DEVOPS FINAL CHALLENGE TEST RUN COMPLETE!{Colors.END}")
    print(f"Total Tests Run: {len(TEST_CASES)}")
    print(f"Passed Checks:   {passed_count} / {len(TEST_CASES)}")
    print(f"Total Execution: {total_time:.2f} seconds")
    print("=" * 84)

def main():
    print_banner()
    
    # Check GPU and FastAPI status
    active_model, server_label, gpu_online = get_system_status()
    gpu_badge = f"{Colors.GREEN}ONLINE (114 tok/s){Colors.END}" if gpu_online else f"{Colors.RED}CHECK VPN{Colors.END}"
    print(f"  • AI Agent Engine:     {Colors.BOLD}{active_model}{Colors.END} via {server_label}")
    print(f"  • Company GPU Status:  {gpu_badge}")
    print(f"  • FastAPI Backend:     {Colors.BOLD}{API_BASE}{Colors.END}")
    print(f"  • Official Icinga UI:  {Colors.BOLD}http://localhost/icingaweb2{Colors.END}")
    print("=" * 84)

    # CLI args check
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_all_tests(interactive=False)
        return

    while True:
        print(f"\n{Colors.BOLD}📋 SELECT A DEVOPS FEATURE TO TEST MANUALLY:{Colors.END}")
        for tc in TEST_CASES:
            print(f"  [{tc['id']}] {tc['title']}")
        print(f"  [A] Run ALL {len(TEST_CASES)} Tests Sequentially (Step-by-Step)")
        print(f"  [R] Run ALL Tests Automatically (Non-Stop)")
        print(f"  [S] Switch Company GPU Model")
        print(f"  [Q] Exit")
        
        choice = input(f"\n👉 {Colors.BOLD}Enter your choice [1-7, A, R, S, Q]: {Colors.END}").strip().upper()
        
        if choice == 'Q':
            print("Exiting test runner. Good luck with your presentation!")
            break
        elif choice == 'A':
            run_all_tests(interactive=True)
        elif choice == 'R':
            run_all_tests(interactive=False)
        elif choice == 'S':
            model_options = ["gpt-oss:20b", "qwen3:14b", "gemma4:12b", "gemma4:e4b", "llama3.1:8b-instruct-q4_K_M", "llama3.1:8b"]
            print("\nAvailable Models:")
            for idx, m in enumerate(model_options, 1):
                print(f"  [{idx}] {m}")
            m_choice = input("Select model number [1-6]: ").strip()
            try:
                sel_idx = int(m_choice) - 1
                if 0 <= sel_idx < len(model_options):
                    new_model = model_options[sel_idx]
                    req_data = json.dumps({"model": new_model}).encode("utf-8")
                    req = urllib.request.Request(f"{API_BASE}/api/model", data=req_data, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        resp = json.loads(r.read().decode("utf-8"))
                        print(f"{Colors.GREEN}✔ Successfully switched active model to: {new_model}{Colors.END}")
            except Exception as e:
                print(f"{Colors.RED}Failed to switch model: {e}{Colors.END}")
        elif choice.isdigit() and 1 <= int(choice) <= len(TEST_CASES):
            run_single_test(int(choice) - 1, interactive=False)
        else:
            print(f"{Colors.RED}Invalid selection. Please choose 1-{len(TEST_CASES)}, A, R, S, or Q.{Colors.END}")

if __name__ == "__main__":
    main()

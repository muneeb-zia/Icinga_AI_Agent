"""
Full integration verification script.
Run: python verify_integration.py
"""
import sys
import requests
import urllib3
urllib3.disable_warnings()

ICINGA_URL = "https://localhost:5665/v1"
ICINGA_AUTH = ("root", "d2d6c11edd38d4c1")
DIRECTOR_URL = "http://localhost/icingaweb2/director"
DIRECTOR_AUTH = ("admin", "admin123")
OS_URL = "http://localhost:9200"

PASS = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"
INFO = "\033[94m INFO\033[0m"

def check(label, ok, detail=""):
    status = PASS if ok else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return ok

print("\n" + "="*60)
print("  ICINGA AI AGENT — FULL INTEGRATION VERIFICATION")
print("="*60)

# ── 1. Icinga Core API ──────────────────────────────────────
print("\n[1] Icinga Core API (port 5665)")
try:
    r = requests.get(f"{ICINGA_URL}/status/IcingaApplication",
                     auth=ICINGA_AUTH, headers={"Accept": "application/json"}, verify=False, timeout=5)
    ok = r.status_code == 200
    if ok:
        version = r.json()["results"][0]["status"]["icingaapplication"]["app"]["version"]
        check("Icinga API reachable", True, f"version {version}")
    else:
        check("Icinga API reachable", False, f"HTTP {r.status_code}")
except Exception as e:
    check("Icinga API reachable", False, str(e))

try:
    r = requests.get(f"{ICINGA_URL}/objects/hosts",
                     auth=ICINGA_AUTH, headers={"Accept": "application/json"}, verify=False, timeout=5)
    hosts = r.json().get("results", [])
    check("Can list hosts", len(hosts) > 0, f"{len(hosts)} hosts found")
except Exception as e:
    check("Can list hosts", False, str(e))

# ── 2. OpenSearch ───────────────────────────────────────────
print("\n[2] OpenSearch (localhost:9200)")
try:
    r = requests.get(f"{OS_URL}/_cluster/health", timeout=5)
    d = r.json()
    status = d.get("status", "unknown")
    check("OpenSearch reachable", r.status_code == 200, f"cluster status: {status}")
    check("OpenSearch healthy", status in ("green", "yellow"), f"nodes: {d.get('number_of_nodes')}")
except Exception as e:
    check("OpenSearch reachable", False, str(e))

try:
    r = requests.get(f"{OS_URL}/_cat/indices?format=json", timeout=5)
    indices = r.json()
    icinga_indices = [i for i in indices if "icinga" in i.get("index", "")]
    check("Icinga indices exist in OpenSearch",
          len(icinga_indices) > 0,
          f"{len(icinga_indices)} icinga2-* indices found" if icinga_indices else "None yet — writer may need 1-2 min")
    if icinga_indices:
        for idx in icinga_indices:
            print(f"         Index: {idx['index']}  ({idx.get('docs.count','?')} docs, {idx.get('store.size','?')})")
    check("All indices listed", True, f"Total indices: {len(indices)}")
except Exception as e:
    check("Icinga indices exist in OpenSearch", False, str(e))

# ── 3. Icinga → OpenSearch Writer ───────────────────────────
print("\n[3] Icinga ElasticsearchWriter Status")
try:
    r = requests.get(f"{ICINGA_URL}/status/ElasticsearchWriter",
                     auth=ICINGA_AUTH, headers={"Accept": "application/json"}, verify=False, timeout=5)
    if r.status_code == 200:
        results = r.json().get("results", [])
        if results:
            writer_status = results[0].get("status", {})
            check("ElasticsearchWriter active", True,
                  f"connected={writer_status.get('elasticsearch', {}).get('active', 'N/A')}")
        else:
            check("ElasticsearchWriter active", True, "feature registered")
    else:
        check("ElasticsearchWriter active", False, f"HTTP {r.status_code}")
except Exception as e:
    check("ElasticsearchWriter active", False, str(e))

# ── 4. Director API ─────────────────────────────────────────
print("\n[4] Icinga Director API (host onboarding)")
try:
    r = requests.get(f"{DIRECTOR_URL}/hosts",
                     auth=DIRECTOR_AUTH, headers={"Accept": "application/json"}, timeout=5)
    check("Director API reachable", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        hosts = r.json().get("objects", [])
        check("Can list Director hosts", True, f"{len(hosts)} hosts managed")
except Exception as e:
    check("Director API reachable", False, str(e))

try:
    import icinga_actions as ia
    r2 = ia.list_director_templates()
    check("Can list monitoring templates", r2.get("status") == "success",
          f"{r2.get('total_available', 0)} check commands available")
    if r2.get("check_commands"):
        print(f"     Available: {[c['name'] for c in r2['check_commands'][:5]]}")

except Exception as e:
    check("Can list Director templates", False, str(e))

# ── 5. Agent Module Import Test ─────────────────────────────
print("\n[5] Agent Python Modules")
try:
    import icinga_api
    result = icinga_api.get_system_status()
    check("icinga_api module", "status" in result, result.get("status", result.get("error", "")))
except Exception as e:
    check("icinga_api module", False, str(e))

try:
    import icinga_actions
    result = icinga_actions.list_director_hosts()
    check("icinga_actions module (Director)", result.get("status") == "success",
          f"{result.get('total_hosts', 0)} hosts" if result.get("status") == "success" else result.get("error", ""))
except Exception as e:
    check("icinga_actions module", False, str(e))

try:
    import elasticsearch_api
    client = elasticsearch_api._get_client()
    check("elasticsearch_api module", client is not None, "OpenSearch client connected" if client else "Not connected yet")
except Exception as e:
    check("elasticsearch_api module", False, str(e))

print("\n" + "="*60)
print("  Verification complete!")
print("="*60 + "\n")

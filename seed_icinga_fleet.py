import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://localhost:5665/v1"
AUTH = ("root", "***REDACTED***")
HEADERS = {"Accept": "application/json"}

hosts = [
    {
        "name": "web-prod-01",
        "display_name": "Production Web Frontend 01",
        "address": "10.0.1.11",
        "state": 0, # UP
        "output": "PING OK - Packet loss = 0%, RTA = 0.42 ms",
        "services": [
            {"name": "http", "state": 0, "output": "HTTP OK: HTTP/1.1 200 OK - 0.082 second response time"},
            {"name": "disk", "state": 0, "output": "DISK OK - free space: / 42.5 GB (68% inode=88%)"}
        ]
    },
    {
        "name": "web-prod-02",
        "display_name": "Production Web Frontend 02",
        "address": "10.0.1.12",
        "state": 0, # UP
        "output": "PING OK - Packet loss = 0%, RTA = 0.51 ms",
        "services": [
            {"name": "http", "state": 0, "output": "HTTP OK: HTTP/1.1 200 OK - 0.091 second response time"},
            {"name": "disk", "state": 0, "output": "DISK OK - free space: / 38.1 GB (62% inode=85%)"}
        ]
    },
    {
        "name": "api-auth-01",
        "display_name": "OAuth2 Auth Microservice",
        "address": "10.0.1.20",
        "state": 0, # UP
        "output": "PING OK - Packet loss = 0%, RTA = 0.38 ms",
        "services": [
            {"name": "http", "state": 0, "output": "HTTP OK: /healthz returned 200 OK"},
            {"name": "memory", "state": 1, "output": "MEMORY WARNING - 84.5% used (6.76 GB of 8.00 GB)"}
        ]
    },
    {
        "name": "api-payment-01",
        "display_name": "PCI Payment Gateway",
        "address": "10.0.1.25",
        "state": 0, # UP
        "output": "PING OK - Packet loss = 0%, RTA = 0.65 ms",
        "services": [
            {"name": "http", "state": 0, "output": "HTTP OK: Stripe/Banking Webhook Live (200 OK)"},
            {"name": "ssl", "state": 0, "output": "SSL OK - Certificate 'api.payment.corp' valid for 88 days"}
        ]
    },
    {
        "name": "db-mysql-primary",
        "display_name": "MySQL Primary DB Cluster",
        "address": "10.0.2.10",
        "state": 0, # UP
        "output": "PING OK - Packet loss = 0%, RTA = 0.29 ms",
        "services": [
            {"name": "mysql", "state": 0, "output": "Uptime: 1428590  Threads: 18  Questions: 28941029  Slow queries: 4"},
            {"name": "disk", "state": 0, "output": "DISK OK - free space: /var/lib/mysql 350.2 GB (78%)"}
        ]
    },
    {
        "name": "db-mysql-replica",
        "display_name": "MySQL Read Replica Node",
        "address": "10.0.2.11",
        "state": 1, # DOWN
        "output": "CRITICAL - Host Unreachable / IO thread terminated",
        "services": [
            {"name": "replication", "state": 2, "output": "CRITICAL - Seconds_Behind_Master: 4820 (Lag exceeds threshold 300s)"},
            {"name": "mysql", "state": 2, "output": "CRITICAL - Cannot connect to MySQL server on 10.0.2.11:3306"}
        ]
    },
    {
        "name": "k8s-worker-01",
        "display_name": "Kubernetes Production Worker 01",
        "address": "10.0.3.15",
        "state": 0, # UP
        "output": "PING OK - Packet loss = 0%, RTA = 0.35 ms",
        "services": [
            {"name": "kubelet", "state": 0, "output": "Kubelet Ready: NodeConditions Ready=True, DiskPressure=False"},
            {"name": "containerd", "state": 0, "output": "Container Runtime active (running)"}
        ]
    }
]

def seed():
    print("=== Seeding Enterprise Fleet into Icinga 2 Core ===")
    for h in hosts:
        h_name = h["name"]
        # Use dummy check command for demo hosts so states reflect realistic enterprise monitoring
        chk_cmd = "dummy" if h["state"] == 0 else "hostalive"
        url_host = f"{BASE_URL}/objects/hosts/{h_name}"
        host_data = {
            "attrs": {
                "display_name": h["display_name"],
                "address": h["address"],
                "check_command": chk_cmd
            }
        }
        r = requests.post(url_host, auth=AUTH, headers=HEADERS, verify=False, json=host_data)
        if r.status_code == 404:
            r = requests.put(url_host, auth=AUTH, headers=HEADERS, verify=False, json=host_data)
        
        # Reschedule check to evaluate state immediately
        url_resched = f"{BASE_URL}/actions/reschedule-check?host={h_name}"
        requests.post(url_resched, auth=AUTH, headers=HEADERS, verify=False, json={"force": True})
        
        # Process explicit check result
        url_check = f"{BASE_URL}/actions/process-check-result?host={h_name}"
        check_data = {
            "exit_status": h["state"],
            "plugin_output": h["output"]
        }
        requests.post(url_check, auth=AUTH, headers=HEADERS, verify=False, json=check_data)
        
        # Create and process services
        for s in h.get("services", []):
            s_name = s["name"]
            url_srv = f"{BASE_URL}/objects/services/{h_name}!{s_name}"
            srv_chk = "dummy" if s["state"] == 0 else "ping"
            srv_data = {
                "attrs": {
                    "check_command": srv_chk
                }
            }
            r_s = requests.post(url_srv, auth=AUTH, headers=HEADERS, verify=False, json=srv_data)
            if r_s.status_code == 404:
                requests.put(url_srv, auth=AUTH, headers=HEADERS, verify=False, json=srv_data)
            
            url_srv_check = f"{BASE_URL}/actions/process-check-result?service={h_name}!{s_name}"
            srv_check_data = {
                "exit_status": s["state"],
                "plugin_output": s["output"]
            }
            requests.post(url_srv_check, auth=AUTH, headers=HEADERS, verify=False, json=srv_check_data)

    print("\n✅ Enterprise Fleet Seed Complete!")

if __name__ == "__main__":
    seed()

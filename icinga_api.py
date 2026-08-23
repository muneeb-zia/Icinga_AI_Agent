import requests
import urllib3
import json
from typing import Optional, Dict, Any

import os

# Disable SSL warnings since we are on localhost
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ICINGA_API_URL = os.environ.get("ICINGA_API_URL", "https://icinga-lab:5665/v1" if os.path.exists("/.dockerenv") else "https://localhost:5665/v1")
AUTH = ("root", os.environ.get("ICINGA_API_PASSWORD", "***REDACTED***"))

def _make_request(endpoint: str, method: str = "GET", params: Optional[Dict] = None, data: Optional[Dict] = None) -> Any:
    """Helper method to make requests to the Icinga API."""
    url = f"{ICINGA_API_URL}/{endpoint}"
    headers = {'Accept': 'application/json'}
    
    # Icinga 2 requires this header on POST requests used as filtered GET queries.
    # Without it, POST returns 400 "Missing both 'attrs' and 'restore_attrs'".
    if method == "POST" and data is not None and 'attrs' not in data:
        headers['X-HTTP-Method-Override'] = 'GET'
    
    try:
        response = requests.request(
            method=method,
            url=url,
            auth=AUTH,
            verify=False,
            headers=headers,
            params=params,
            json=data
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "status_code": getattr(e.response, 'status_code', None)}

def get_system_status() -> Dict:
    """Queries the Icinga API for a high-level dashboard overview."""
    data = _make_request("status/IcingaApplication")
    if "error" in data:
        return data
        
    try:
        app_info = data['results'][0]['status']['icingaapplication']['app']
        return {
            "status": "connected",
            "version": app_info.get('version'),
            "node_name": app_info.get('node_name'),
            "enable_ha": app_info.get('enable_ha')
        }
    except (KeyError, IndexError) as e:
        return {"error": f"Unexpected response format: {e}"}

def get_all_hosts(filter_state: Optional[str] = None) -> Dict:
    """
    Queries all hosts. 
    Optional filter_state: 'UP', 'DOWN', or 'UNREACHABLE'.
    """
    data = _make_request("objects/hosts")
    if "error" in data:
        return data
        
    hosts = []
    state_map = {0: "UP", 1: "DOWN", 2: "UNREACHABLE"}
    reverse_map = {v: k for k, v in state_map.items()}
    
    target_state = None
    if filter_state:
        target_state = reverse_map.get(filter_state.upper())
    
    for result in data.get('results', []):
        attrs = result.get('attrs', {})
        current_state = attrs.get('state')
        
        if target_state is not None and current_state != target_state:
            continue
            
        hosts.append({
            "name": attrs.get('name'),
            "display_name": attrs.get('display_name'),
            "address": attrs.get('address'),
            "state": state_map.get(current_state, "UNKNOWN"),
            "check_command": attrs.get('check_command')
        })
        
    return {"total_hosts": len(hosts), "hosts": hosts}

def get_host_details(hostname: str) -> Dict:
    """Retrieves specific details for a single host."""
    data = _make_request(f"objects/hosts/{hostname}")
    if "error" in data:
        return data
        
    if not data.get('results'):
        return {"error": f"Host '{hostname}' not found."}
        
    attrs = data['results'][0].get('attrs', {})
    
    return {
        "name": attrs.get('name'),
        "templates": attrs.get('templates'),
        "vars": attrs.get('vars'),
        "state": attrs.get('state'),
        "output": attrs.get('last_check_result', {}).get('output')
    }

def get_critical_services() -> Dict:
    """Queries for active critical alerts (service state == 2)."""
    # Icinga API allows filtering, but we can also just fetch all and filter in Python to be safe if complex filters fail.
    # We will use the API filter for efficiency.
    payload = {
        "filter": "service.state == 2"
    }
    data = _make_request("objects/services", method="POST", data=payload)
    # Using POST for objects endpoint with filter body is supported in Icinga API.
    # Alternatively GET with URL params: ?filter=service.state==2
    # Let's fallback to GET if POST fails, or just use GET params.
    if "error" in data:
        # Fallback to GET with params
        data = _make_request("objects/services", params={"filter": "service.state==2"})
        if "error" in data:
            return data
            
    critical_services = []
    for result in data.get('results', []):
        attrs = result.get('attrs', {})
        critical_services.append({
            "host_name": attrs.get('host_name'),
            "service_name": attrs.get('name'),
            "state": "CRITICAL",
            "output": attrs.get('last_check_result', {}).get('output')
        })
        
    return {"total_critical": len(critical_services), "services": critical_services}

def get_templates_and_zones() -> Dict:
    """Lists available host templates."""
    data = _make_request("objects/hosttemplates")
    if "error" in data:
        return data
        
    templates = []
    for result in data.get('results', []):
        templates.append(result.get('attrs', {}).get('name'))
        
    return {"total_templates": len(templates), "templates": templates}


# =============================================================================
# NEW READ USE CASES (Phase 1 Extension)
# =============================================================================

def get_service_details(hostname: str, service_name: str) -> Dict:
    """
    Retrieves detailed status of a specific service on a specific host.
    
    Use Case 6: Service-Level Deep Dive
    Example: "What is the status of the SSH service on db-master?"
    """
    # Use POST filter — handles service names with spaces/slashes (e.g. "disk /")
    # The URL path format `host!service` breaks for special characters
    payload = {
        "filter": f'host.name=="{hostname}" && service.name=="{service_name}"'
    }
    data = _make_request("objects/services", method="POST", data=payload)
    
    if "error" in data:
        # Fallback: try URL-encoding safe path format for simple names
        import urllib.parse
        safe_svc = urllib.parse.quote(service_name, safe="")
        data = _make_request(f"objects/services/{hostname}!{safe_svc}")
        if "error" in data:
            return data
    
    if not data.get('results'):
        return {"error": f"Service '{service_name}' on host '{hostname}' not found."}
    
    attrs = data['results'][0].get('attrs', {})
    state_map = {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"}
    
    last_check = attrs.get('last_check_result', {})
    
    return {
        "host": hostname,
        "service": service_name,
        "display_name": attrs.get('display_name', service_name),
        "state": state_map.get(attrs.get('state'), "UNKNOWN"),
        "state_type": "HARD" if attrs.get('state_type', 0) == 1 else "SOFT",
        "output": last_check.get('output', ''),
        "long_output": last_check.get('long_output', ''),
        "check_command": attrs.get('check_command'),
        "last_check": attrs.get('last_check'),
        "next_check": attrs.get('next_check'),
        "check_interval": attrs.get('check_interval'),
        "retry_interval": attrs.get('retry_interval'),
        "max_check_attempts": attrs.get('max_check_attempts'),
        "current_attempt": attrs.get('check_attempt'),
        "performance_data": last_check.get('performance_data', []),
        "acknowledgement": attrs.get('acknowledgement', 0) > 0,
        "downtime_depth": attrs.get('downtime_depth', 0),
        "flapping": attrs.get('flapping', False),
        "vars": attrs.get('vars', {}),
    }


def get_host_services(hostname: str) -> Dict:
    """
    Lists ALL services being monitored on a specific host.
    
    Use Case 7: Host Service Inventory
    Example: "List all services being monitored on web-01"
    """
    # Filter services by host
    payload = {
        "filter": f'host.name=="{hostname}"'
    }
    data = _make_request("objects/services", method="POST", data=payload)
    
    if "error" in data:
        # Fallback to GET
        data = _make_request("objects/services", params={"filter": f'host.name=="{hostname}"'})
        if "error" in data:
            return data
    
    state_map = {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"}
    
    services = []
    for result in data.get('results', []):
        attrs = result.get('attrs', {})
        services.append({
            "name": attrs.get('name'),
            "display_name": attrs.get('display_name'),
            "state": state_map.get(attrs.get('state'), "UNKNOWN"),
            "output": attrs.get('last_check_result', {}).get('output', ''),
            "check_command": attrs.get('check_command'),
            "acknowledged": attrs.get('acknowledgement', 0) > 0,
            "in_downtime": attrs.get('downtime_depth', 0) > 0,
        })
    
    # Group by state for summary
    state_summary = {}
    for s in services:
        state = s['state']
        state_summary[state] = state_summary.get(state, 0) + 1
    
    return {
        "host": hostname,
        "total_services": len(services),
        "state_summary": state_summary,
        "services": services
    }


def get_notification_history(hostname: Optional[str] = None, limit: int = 10) -> Dict:
    """
    Retrieves recent notifications (emails, SMS, etc.) sent by Icinga.
    Optionally filter by hostname.
    
    Use Case 8: Notification Audit Trail
    Example: "Who was notified about the last critical alert?"
    """
    # Notifications are available via /v1/objects/notifications
    # But the actual sent notifications are in the event stream or log
    # We'll query notifications objects to see configured notifications
    # and use the comment/contact info
    
    if hostname:
        payload = {"filter": f'host.name=="{hostname}"'}
        data = _make_request("objects/notifications", method="POST", data=payload)
        if "error" in data:
            data = _make_request("objects/notifications", params={"filter": f'host.name=="{hostname}"'})
    else:
        data = _make_request("objects/notifications")
    
    if "error" in data:
        return data
    
    notifications = []
    for result in data.get('results', [])[:limit]:
        attrs = result.get('attrs', {})
        notifications.append({
            "name": attrs.get('name'),
            "host_name": attrs.get('host_name'),
            "service_name": attrs.get('service_name', 'host-check'),
            "notification_command": attrs.get('command'),
            "users": attrs.get('users', []),
            "user_groups": attrs.get('user_groups', []),
            "last_notification": attrs.get('last_notification'),
            "next_notification": attrs.get('next_notification'),
            "notification_number": attrs.get('notification_number', 0),
            "types": attrs.get('types', []),
            "states": attrs.get('states', []),
        })
    
    return {
        "filter": hostname or "all hosts",
        "total_notifications": len(notifications),
        "notifications": notifications
    }


def get_downtime_status() -> Dict:
    """
    Lists all hosts and services currently in an active scheduled downtime.
    
    Use Case 9: Active Downtime Inspector
    Example: "Which hosts are currently in scheduled downtime?"
    """
    # Query hosts with downtime_depth > 0
    payload = {
        "filter": "host.downtime_depth > 0"
    }
    host_data = _make_request("objects/hosts", method="POST", data=payload)
    
    if "error" in host_data:
        host_data = _make_request("objects/hosts")
    
    state_map = {0: "UP", 1: "DOWN", 2: "UNREACHABLE"}
    
    hosts_in_downtime = []
    if "error" not in host_data:
        for result in host_data.get('results', []):
            attrs = result.get('attrs', {})
            if attrs.get('downtime_depth', 0) > 0:
                hosts_in_downtime.append({
                    "name": attrs.get('name'),
                    "state": state_map.get(attrs.get('state'), "UNKNOWN"),
                    "downtime_depth": attrs.get('downtime_depth'),
                    "address": attrs.get('address'),
                })
    
    # Query services with downtime_depth > 0
    svc_payload = {
        "filter": "service.downtime_depth > 0"
    }
    svc_data = _make_request("objects/services", method="POST", data=svc_payload)
    
    svc_state_map = {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"}
    
    services_in_downtime = []
    if "error" not in svc_data:
        for result in svc_data.get('results', []):
            attrs = result.get('attrs', {})
            if attrs.get('downtime_depth', 0) > 0:
                services_in_downtime.append({
                    "host": attrs.get('host_name'),
                    "service": attrs.get('name'),
                    "state": svc_state_map.get(attrs.get('state'), "UNKNOWN"),
                })
    
    return {
        "hosts_in_downtime": len(hosts_in_downtime),
        "services_in_downtime": len(services_in_downtime),
        "hosts": hosts_in_downtime,
        "services": services_in_downtime,
        "message": (
            f"{len(hosts_in_downtime)} host(s) and {len(services_in_downtime)} service(s) "
            "are currently in scheduled downtime."
        )
    }


def get_check_statistics() -> Dict:
    """
    Get Icinga checker performance statistics — latency, execution time, 
    active checks count, etc.
    
    Use Case 10: Monitoring Health Check
    Example: "Is our Icinga system itself healthy? What's the check latency?"
    """
    # CIB (Common Information Base) has the operational stats
    data = _make_request("status/CIB")
    if "error" in data:
        return data
    
    try:
        status = data['results'][0]['status']
        
        return {
            "active_host_checks": status.get('active_host_checks'),
            "active_service_checks": status.get('active_service_checks'),
            "passive_host_checks": status.get('passive_host_checks'),
            "passive_service_checks": status.get('passive_service_checks'),
            "avg_latency": status.get('avg_latency'),
            "avg_execution_time": status.get('avg_execution_time'),
            "min_latency": status.get('min_latency'),
            "max_latency": status.get('max_latency'),
            "min_execution_time": status.get('min_execution_time'),
            "max_execution_time": status.get('max_execution_time'),
            "num_hosts_up": status.get('num_hosts_up'),
            "num_hosts_down": status.get('num_hosts_down'),
            "num_hosts_unreachable": status.get('num_hosts_unreachable'),
            "num_services_ok": status.get('num_services_ok'),
            "num_services_warning": status.get('num_services_warning'),
            "num_services_critical": status.get('num_services_critical'),
            "num_services_unknown": status.get('num_services_unknown'),
            "uptime": status.get('uptime'),
        }
    except (KeyError, IndexError) as e:
        return {"error": f"Unexpected CIB response format: {e}"}


if __name__ == "__main__":
    print("Testing System Status:")
    print(json.dumps(get_system_status(), indent=2))
    
    print("\nTesting Get All Hosts:")
    print(json.dumps(get_all_hosts(), indent=2))
    
    print("\nTesting Get Check Statistics:")
    print(json.dumps(get_check_statistics(), indent=2))
    
    print("\nTesting Get Downtime Status:")
    print(json.dumps(get_downtime_status(), indent=2))

import requests
import urllib3
import json
from typing import Optional, Dict, Any

# Disable SSL warnings since we are on localhost
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ICINGA_API_URL = "https://localhost:5665/v1"
AUTH = ("root", "b9ee894b2eff2cf9")

def _make_request(endpoint: str, method: str = "GET", params: Optional[Dict] = None, data: Optional[Dict] = None) -> Any:
    """Helper method to make requests to the Icinga API."""
    url = f"{ICINGA_API_URL}/{endpoint}"
    headers = {'Accept': 'application/json'}
    
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

if __name__ == "__main__":
    print("Testing System Status:")
    print(json.dumps(get_system_status(), indent=2))
    
    print("\nTesting Get All Hosts:")
    print(json.dumps(get_all_hosts(), indent=2))

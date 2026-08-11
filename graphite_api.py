import requests
import time
import random
from typing import Dict, Any

# Placeholder for the future real Graphite API URL
GRAPHITE_URL = "http://localhost:8080"
DEMO_MODE = False # Set to False when using real API

def get_historical_data(target_metric: str, from_time: str = "-24h") -> Dict[str, Any]:
    """
    Fetches time-series data from Graphite.
    """
    if DEMO_MODE:
        return _generate_mock_data(target_metric, from_time)
        
    endpoint = f"{GRAPHITE_URL}/render"
    params = {
        "target": target_metric,
        "format": "json",
        "from": from_time
    }
    
    try:
        # Attempt to connect to the real API
        response = requests.get(endpoint, params=params, timeout=5)
        response.raise_for_status()
        return {"status": "success", "data": response.json(), "source": "real"}
    except requests.exceptions.ConnectionError:
        return {"error": f"Connection Refused: Could not connect to Graphite at {GRAPHITE_URL}. Ensure the service is running."}
    except requests.exceptions.Timeout:
        return {"error": f"Timeout: Graphite API at {GRAPHITE_URL} took too long to respond."}
    except requests.exceptions.RequestException as e:
        return {"error": f"API Error: {str(e)}"}

def _generate_mock_data(target_metric: str, from_time: str) -> Dict[str, Any]:
    """Generates fake time-series data simulating a CPU spike for local testing."""
    current_time = int(time.time())
    start_time = current_time - (24 * 3600)
    datapoints = []
    
    for i in range(24):
        timestamp = start_time + (i * 3600)
        # Simulate a normal CPU load around 20-30%, but a spike to 95% at hour 18
        if i in [17, 18, 19]:
            value = random.uniform(85.0, 98.0)
        else:
            value = random.uniform(15.0, 35.0)
        datapoints.append([value, timestamp])
        
    mock_response = [{"target": target_metric, "datapoints": datapoints}]
    return {"status": "success", "data": mock_response, "source": "Demo Data"}

if __name__ == "__main__":
    print(f"Testing Graphite API Integration (Demo Mode: {DEMO_MODE})...")
    result = get_historical_data("icinga2.master-node.cpu.usage")
    if "error" in result:
        print(f"Failed to fetch data: {result['error']}")
    else:
        print(f"Data Source: {result['source']}")
        print(f"Number of Datapoints: {len(result.get('data', [{}])[0].get('datapoints', []))}")

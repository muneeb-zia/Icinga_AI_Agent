import requests
from typing import Dict, Any

# Placeholder for the future real Graphite API URL
GRAPHITE_URL = "http://localhost:8080"

def get_historical_data(target_metric: str, from_time: str = "-24h") -> Dict[str, Any]:
    """
    Fetches time-series data from Graphite.
    """
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

if __name__ == "__main__":
    print("Testing Real Graphite API Integration...")
    result = get_historical_data("icinga2.master-node.cpu.usage")
    if "error" in result:
        print(f"Failed to fetch data: {result['error']}")
    else:
        print(f"Data Source: {result['source']}")
        print(f"Number of Datapoints: {len(result.get('data', [{}])[0].get('datapoints', []))}")

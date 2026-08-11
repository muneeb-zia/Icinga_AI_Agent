import requests
import urllib3

# Disable SSL warnings since we are on localhost
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# The API endpoint for your local Docker container
ICINGA_API_URL = "https://localhost:5665/v1"
AUTH = ("root", "0b72c5d5d2d2fa88")

def get_system_status():
    """Queries the Icinga API for system status to ensure the bridge works."""
    url = f"{ICINGA_API_URL}/status/IcingaApplication"
    
    try:
        response = requests.get(url, auth=AUTH, verify=False)
        if response.status_code == 200:
            data = response.json()
            app_info = data['results'][0]['status']['icingaapplication']['app']
            print("SUCCESS! Bridge is connected.")
            print(f"Icinga Version: {app_info['version']}")
            print(f"Node Name: {app_info['node_name']}")
        else:
            print(f"Failed to connect. Status Code: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Connection error: {e}")

# Run the test
if __name__ == "__main__":
    get_system_status()
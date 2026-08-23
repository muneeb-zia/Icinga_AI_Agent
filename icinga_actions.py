"""
Icinga Actions Module — Phase 2 Action-Capable Agent.

This module contains all WRITE/ACTION operations that modify the Icinga 2 state.
Separated from icinga_api.py for clean security boundaries.

All actions use the Icinga 2 Actions API:
https://icinga.com/docs/icinga-2/latest/doc/12-icinga2-api/#actions

IMPORTANT: These functions execute real changes. The agent should always
confirm with the user before calling these (Human-in-the-Loop safety).
"""

import requests
import urllib3
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import os
# Disable SSL warnings for internal dev environment
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configuration ---
ICINGA_API_URL = os.environ.get("ICINGA_API_URL", "https://icinga-lab:5665/v1" if os.path.exists("/.dockerenv") else "https://localhost:5665/v1")
ACTION_AUTH = ("root", os.environ.get("ICINGA_API_PASSWORD", "***REDACTED***"))


def _action_request(endpoint: str, data: Dict, method: str = "POST") -> Any:
    """
    Helper to make action requests to the Icinga 2 API.
    Actions always use POST method.
    """
    url = f"{ICINGA_API_URL}/{endpoint}"
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.request(
            method=method,
            url=url,
            auth=ACTION_AUTH,
            verify=False,
            headers=headers,
            json=data
        )
        response.raise_for_status()
        result = response.json()

        # Icinga actions return a list of results
        results = result.get("results", [])
        if results:
            # Check if any result has a non-200 status
            errors = [r for r in results if r.get("code", 200) >= 400]
            if errors:
                return {
                    "status": "partial_failure",
                    "errors": errors,
                    "successes": [r for r in results if r.get("code", 200) < 400]
                }
            return {
                "status": "success",
                "results": results
            }
        return {"status": "success", "results": results}

    except requests.exceptions.ConnectionError:
        return {
            "error": "Connection refused. Icinga API is not reachable at " + ICINGA_API_URL,
            "hint": "Ensure the Icinga container is running: docker-compose up -d"
        }
    except requests.exceptions.RequestException as e:
        return {
            "error": str(e),
            "status_code": getattr(e.response, 'status_code', None)
        }


# =============================================================================
# ACTION 1: Acknowledge Problem
# =============================================================================

def acknowledge_problem(
    hostname: str,
    service: Optional[str] = None,
    author: str = "AI Agent",
    comment: str = "Acknowledged by Icinga AI Agent",
    notify: bool = True,
    sticky: bool = True,
    persistent: bool = False
) -> Dict[str, Any]:
    """
    Acknowledge a host or service problem in Icinga 2.

    This stops Icinga from sending repeated notifications for this issue.
    The acknowledgement remains until the problem is resolved or manually removed.

    Args:
        hostname: The host with the problem.
        service: Optional service name. If None, acknowledges the host problem.
        author: Who is acknowledging (logged in Icinga history).
        comment: Reason for acknowledgement.
        notify: Whether to send an acknowledgement notification.
        sticky: If True, ack stays even if the state changes (e.g., CRITICAL→WARNING).
        persistent: If True, ack survives Icinga restarts.

    Returns:
        Dict with success/error status.
    """
    # Build the filter based on whether it's a host or service acknowledgement
    if service:
        filter_str = f'host.name=="{hostname}" && service.name=="{service}"'
        obj_type = "Service"
    else:
        filter_str = f'host.name=="{hostname}"'
        obj_type = "Host"

    payload = {
        "type": obj_type,
        "filter": filter_str,
        "author": author,
        "comment": comment,
        "notify": notify,
        "sticky": sticky,
        "persistent": persistent
    }

    result = _action_request("actions/acknowledge-problem", payload)

    if "error" not in result:
        target = f"{hostname}!{service}" if service else hostname
        result["action"] = "acknowledge_problem"
        result["target"] = target
        result["message"] = f"Successfully acknowledged problem on {target}."

    return result


# =============================================================================
# ACTION 2: Schedule Downtime
# =============================================================================

def schedule_downtime(
    hostname: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    duration_hours: float = 2.0,
    author: str = "AI Agent",
    comment: str = "Scheduled downtime via AI Agent",
    service: Optional[str] = None,
    all_services: bool = True
) -> Dict[str, Any]:
    """
    Schedule a downtime window for a host (and optionally its services).

    During downtime, Icinga suppresses notifications for the host/service.

    Args:
        hostname: The host to schedule downtime for.
        start_time: Start time as ISO string (e.g., '2025-01-15T02:00:00'). Defaults to now.
        end_time: End time as ISO string. If not provided, calculated from duration_hours.
        duration_hours: Duration in hours (used if end_time is not provided). Default 2h.
        author: Who is scheduling the downtime.
        comment: Reason for the downtime.
        service: Specific service to put in downtime. If None, applies to the host.
        all_services: If True and no specific service, also schedule downtime for all services on the host.

    Returns:
        Dict with success/error status.
    """
    # Calculate timestamps
    if start_time:
        start_dt = datetime.fromisoformat(start_time)
    else:
        start_dt = datetime.now()

    if end_time:
        end_dt = datetime.fromisoformat(end_time)
    else:
        end_dt = start_dt + timedelta(hours=duration_hours)

    start_epoch = int(start_dt.timestamp())
    end_epoch = int(end_dt.timestamp())
    duration_secs = end_epoch - start_epoch

    if service:
        filter_str = f'host.name=="{hostname}" && service.name=="{service}"'
        obj_type = "Service"
    else:
        filter_str = f'host.name=="{hostname}"'
        obj_type = "Host"

    payload = {
        "type": obj_type,
        "filter": filter_str,
        "author": author,
        "comment": comment,
        "start_time": start_epoch,
        "end_time": end_epoch,
        "duration": duration_secs,
        "fixed": True,
        "all_services": all_services if not service else False
    }

    result = _action_request("actions/schedule-downtime", payload)

    if "error" not in result:
        target = f"{hostname}!{service}" if service else hostname
        result["action"] = "schedule_downtime"
        result["target"] = target
        result["window"] = {
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "duration_hours": duration_hours
        }
        result["message"] = (
            f"Successfully scheduled downtime on {target} "
            f"from {start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')}."
        )

    return result


# =============================================================================
# ACTION 3: Add Comment
# =============================================================================

def add_comment(
    hostname: str,
    author: str = "AI Agent",
    comment: str = "Comment added by AI Agent",
    service: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a comment/note to a host or service in Icinga 2.

    Comments are visible in Icinga Web 2 and useful for logging observations,
    investigation notes, or AI-generated insights.

    Args:
        hostname: The host to comment on.
        author: Who is adding the comment.
        comment: The comment text.
        service: Optional service. If None, comment is added to the host.

    Returns:
        Dict with success/error status.
    """
    if service:
        filter_str = f'host.name=="{hostname}" && service.name=="{service}"'
        obj_type = "Service"
    else:
        filter_str = f'host.name=="{hostname}"'
        obj_type = "Host"

    payload = {
        "type": obj_type,
        "filter": filter_str,
        "author": author,
        "comment": comment
    }

    result = _action_request("actions/add-comment", payload)

    if "error" not in result:
        target = f"{hostname}!{service}" if service else hostname
        result["action"] = "add_comment"
        result["target"] = target
        result["message"] = f"Successfully added comment to {target}: '{comment}'"

    return result


# =============================================================================
# ACTION 4: Remove Acknowledgement
# =============================================================================

def remove_acknowledgement(
    hostname: str,
    service: Optional[str] = None
) -> Dict[str, Any]:
    """
    Remove an existing acknowledgement from a host or service.

    This re-enables notifications for the problem (useful when the
    original ack was premature or the issue was misidentified).

    Args:
        hostname: The host to remove acknowledgement from.
        service: Optional service name. If None, removes host acknowledgement.

    Returns:
        Dict with success/error status.
    """
    if service:
        filter_str = f'host.name=="{hostname}" && service.name=="{service}"'
        obj_type = "Service"
    else:
        filter_str = f'host.name=="{hostname}"'
        obj_type = "Host"

    payload = {
        "type": obj_type,
        "filter": filter_str
    }

    result = _action_request("actions/remove-acknowledgement", payload)

    if "error" not in result:
        target = f"{hostname}!{service}" if service else hostname
        result["action"] = "remove_acknowledgement"
        result["target"] = target
        result["message"] = f"Successfully removed acknowledgement from {target}."

    return result


# =============================================================================
# ACTION 5: Send Custom Notification
# =============================================================================

def send_custom_notification(
    hostname: str,
    author: str = "AI Agent",
    comment: str = "Custom notification sent by AI Agent",
    service: Optional[str] = None,
    force: bool = True
) -> Dict[str, Any]:
    """
    Force-send a custom notification for a host or service.

    Useful when you want to explicitly alert the on-call team about something
    the AI agent has discovered, even if Icinga wouldn't normally notify.

    Args:
        hostname: The host to notify about.
        author: Who is sending the notification.
        comment: The notification message.
        service: Optional service. If None, notification is about the host.
        force: If True, bypass notification filters and time periods.

    Returns:
        Dict with success/error status.
    """
    if service:
        filter_str = f'host.name=="{hostname}" && service.name=="{service}"'
        obj_type = "Service"
    else:
        filter_str = f'host.name=="{hostname}"'
        obj_type = "Host"

    payload = {
        "type": obj_type,
        "filter": filter_str,
        "author": author,
        "comment": comment,
        "force": force
    }

    result = _action_request("actions/send-custom-notification", payload)

    if "error" not in result:
        target = f"{hostname}!{service}" if service else hostname
        result["action"] = "send_custom_notification"
        result["target"] = target
        result["message"] = f"Custom notification sent for {target}."

    return result


# =============================================================================
# ACTION 6: Reschedule Check
# =============================================================================

def reschedule_check(
    hostname: str,
    service: Optional[str] = None,
    force: bool = True
) -> Dict[str, Any]:
    """
    Force an immediate re-check of a host or service.

    Useful after making changes (e.g., restarting a service) to verify
    the fix without waiting for the next scheduled check interval.

    Args:
        hostname: The host to re-check.
        service: Optional service. If None, re-checks the host itself.
        force: If True, overrides the normal check interval.

    Returns:
        Dict with success/error status.
    """
    if service:
        filter_str = f'host.name=="{hostname}" && service.name=="{service}"'
        obj_type = "Service"
    else:
        filter_str = f'host.name=="{hostname}"'
        obj_type = "Host"

    next_check = int(time.time())  # Schedule for right now

    payload = {
        "type": obj_type,
        "filter": filter_str,
        "next_check": next_check,
        "force_check": force
    }

    result = _action_request("actions/reschedule-check", payload)

    if "error" not in result:
        target = f"{hostname}!{service}" if service else hostname
        result["action"] = "reschedule_check"
        result["target"] = target
        result["message"] = f"Forced immediate re-check of {target}."

    return result


# =============================================================================
# DIRECTOR API — Configuration Management (Phase 3 Upgrade)
# =============================================================================
# We now use the Icinga Director API for all configuration management to support
# host groups, service sets, check commands, and templates.

DIRECTOR_API_URL = os.environ.get("DIRECTOR_API_URL", "http://icinga-lab/icingaweb2/director" if os.path.exists("/.dockerenv") else "http://localhost/icingaweb2/director")
DIRECTOR_AUTH = ("admin", "admin123")

def _director_request(endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Dict[str, Any]:
    url = f"{DIRECTOR_API_URL}/{endpoint}"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    try:
        response = requests.request(
            method=method, url=url, auth=DIRECTOR_AUTH, headers=headers, json=data, timeout=10
        )
        if response.status_code >= 400:
            try:
                err_msg = response.json()
            except Exception:
                err_msg = response.text
            return {"error": f"HTTP {response.status_code}", "details": err_msg}
        try:
            return response.json()
        except Exception:
            return {"status": "success", "raw": response.text}
    except Exception as e:
        return {"error": str(e)}

def create_hostgroup(object_name: str, display_name: Optional[str] = None) -> Dict:
    data = {"object_name": object_name, "object_type": "object"}
    if display_name:
        data["display_name"] = display_name
    return _director_request("hostgroup", method="POST", data=data)

def create_host_template(object_name: str, check_command: str = "hostalive") -> Dict:
    data = {"object_name": object_name, "object_type": "template", "check_command": check_command}
    return _director_request("host", method="POST", data=data)

def create_host(object_name: str, address: str, imports: Optional[Any] = None, display_name: Optional[str] = None, groups: Optional[Any] = None, check_command: Optional[str] = None) -> Dict:
    if imports is None:
        imports_list = []
    elif isinstance(imports, str):
        imports_list = [imports]
    else:
        imports_list = list(imports)

    data = {"object_name": object_name, "object_type": "object", "address": address}
    if imports_list:
        data["imports"] = imports_list
    else:
        data["check_command"] = check_command or "hostalive"

    if display_name:
        data["display_name"] = display_name
    if groups:
        data["groups"] = [groups] if isinstance(groups, str) else list(groups)
    return _director_request("host", method="POST", data=data)

def create_servicegroup(object_name: str, display_name: Optional[str] = None) -> Dict:
    data = {"object_name": object_name, "object_type": "object"}
    if display_name: data["display_name"] = display_name
    return _director_request("servicegroup", method="POST", data=data)

def create_service_template(object_name: str, check_command: str) -> Dict:
    data = {"object_name": object_name, "object_type": "template", "check_command": check_command}
    return _director_request("service", method="POST", data=data)

def create_service(object_name: str, host: str, imports: list) -> Dict:
    data = {"object_name": object_name, "object_type": "object", "host": host, "imports": imports}
    return _director_request("service", method="POST", data=data)

def create_serviceset(object_name: str, host: str, description: Optional[str] = None) -> Dict:
    """Creates a service set linked to a host. Director requires a host association."""
    data = {"object_name": object_name, "object_type": "object", "host": host}
    if description:
        data["description"] = description
    return _director_request("serviceset", method="POST", data=data)

def create_check_command(object_name: str, command: str) -> Dict:
    data = {"object_name": object_name, "object_type": "object", "methods_execute": "PluginCheck", "command": command}
    return _director_request("command", method="POST", data=data)

def deploy_director_config() -> Dict:
    return _director_request("config/deploy", method="POST")

def list_director_hosts(filter_name: Optional[str] = None) -> Dict:
    res = _director_request("hosts")
    if "error" in res: return res
    hosts = res.get("objects", [])
    if filter_name:
        hosts = [h for h in hosts if filter_name.lower() in h.get("object_name", "").lower()]
    return {"status": "success", "total_hosts": len(hosts), "hosts": [h.get("object_name") for h in hosts]}

def list_director_templates() -> Dict:
    res = _director_request("hosts")
    if "error" in res: return res
    templates = [h.get("object_name") for h in res.get("objects", []) if h.get("object_type") == "template"]
    return {"status": "success", "templates": templates}

if __name__ == "__main__":
    print("Icinga Actions Module loaded.")


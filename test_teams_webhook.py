import requests
import json
import os

url = "***REDACTED-TEAMS-WEBHOOK***"

# 1. Standard Power Automate Teams payload
payload = {
    "type": "message",
    "attachments": [
        {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "🚨 [CRITICAL] api-auth-01 :: check_http",
                        "weight": "Bolder",
                        "size": "Medium",
                        "color": "Attention"
                    },
                    {
                        "type": "TextBlock",
                        "text": "Routed to: **Development Team** (P1 - HIGH)",
                        "isSubtle": True
                    },
                    {
                        "type": "TextBlock",
                        "text": "HTTP 500 NullPointerException at AuthFilter.java:88",
                        "wrap": True
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {"title": "Host", "value": "api-auth-01"},
                            {"title": "Service", "value": "check_http"},
                            {"title": "Discipline", "value": "Development Team (Auth Squad)"},
                            {"title": "Code Location", "value": "AuthFilter.java:88"}
                        ]
                    }
                ],
                "actions": [
                    {
                        "type": "Action.OpenUrl",
                        "title": "🔍 View Trace in Sentry/Logs",
                        "url": "http://localhost:5601"
                    },
                    {
                        "type": "Action.OpenUrl",
                        "title": "⚡ Open Icinga Dashboard",
                        "url": "http://localhost/icingaweb2"
                    }
                ]
            }
        }
    ]
}

print("Testing direct POST to Power Automate webhook...")
r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
print("Status Code:", r.status_code)
print("Response text:", r.text[:400])

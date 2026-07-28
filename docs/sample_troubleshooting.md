# Icinga 2 Troubleshooting Guide

## General Troubleshooting Strategy
Before diving into specific alerts, perform these fundamental checks:
1. **Check Logs:** The most critical step is examining the logs. Run `tail -f /var/log/icinga2/icinga2.log` on the master or relevant satellite node to see real-time errors or notification attempts.
2. **Verify Configuration:** Always validate your configuration files before restarting: `icinga2 daemon -C`.
3. **Manual Testing:** Run the plugin manually as the `icinga` user to ensure it works outside the Icinga environment: `sudo -u icinga /usr/lib/nagios/plugins/check_disk -w 20% -c 10% -p /`
4. **Check Feature Status:** Ensure necessary features (like `checker` or `api`) are enabled: `icinga2 feature list`.

## Alert: Host Down
**Symptom:** A host is marked as DOWN in Icinga.
**Troubleshooting Steps:**
1. **Network Connectivity:** Verify if the host is reachable via `ping` from the monitoring node (or satellite) responsible for the check.
2. **Check Command:** Ensure the host is using a reliable `check_command` (e.g., `hostalive` or `ping4`). 
3. **Agent Status:** If using the Icinga 2 agent, check if the `icinga2` service is running on the target host. If the agent service stops, checks will become "late" or trigger alerts.
4. **Downtime:** Check if the host was intentionally put into "Downtime" in Icinga Web 2. If it is in downtime but still sending alerts, verify that the notification configuration is correctly respecting the downtime state.

## Alert: Disk Space Full
**Symptom:** A disk check returns a WARNING or CRITICAL state.
**Troubleshooting Steps:**
1. **Check Thresholds:** Verify your warning/critical thresholds in the service definition. If you are receiving alerts for transient spikes, consider increasing the `max_check_attempts` to ensure the issue is persistent before alerting.
2. **Log Bloat:** If you see "Too many open files" or disk full errors on your Icinga master, check `/var/log/icinga2/` for massive log files. You may need to clear logs or adjust log rotation settings.
3. **Plugin Output Discrepancies:** If the GUI shows different data than the command line, use the `icinga2 console` to debug the check result and ensure the API is correctly propagating the performance data.

## Alert: CPU Load High
**Symptom:** CPU load exceeds thresholds.
**Troubleshooting Steps:**
1. **Load vs. Utilization:** Remember that "Load" (the number of processes in the run queue) is generally a better indicator of system health than momentary CPU percentage.
2. **High Load during Deployments:** It is common for the master node to experience CPU spikes during configuration reloads or large deployments (e.g., via Icinga Director). If these spikes are short, they are often normal.
3. **Persistent High Load:** Use `htop` on the affected server to identify the offending processes. If the Icinga agent process itself is at 99% CPU, investigate the number of checks being performed or potential communication loops with the master. In distributed setups, verify that your zone hierarchy is balanced and that satellites aren't overwhelmed by too many local API requests.

# Enterprise AIOps Troubleshooting Runbooks & Root Cause Analysis (RCA) Guide

This repository contains operational runbooks, root cause analysis procedures, and automated diagnostic workflows for enterprise infrastructure monitored by Icinga 2.

---

## 1. Alert: Host Down / Network Unreachability / Ping Timeout
**Symptom / Trigger:** Host state is DOWN or UNREACHABLE; `check_ping` or `hostalive` returns `CRITICAL - 100% packet loss` or `Socket timeout after 10 seconds`.

### Diagnostic Commands:
```bash
# 1. Test ICMP reachability and traceroute
ping -c 4 <target_ip_or_hostname>
traceroute -n <target_ip_or_hostname>

# 2. Verify DNS resolution
dig +short <target_ip_or_hostname>
nslookup <target_ip_or_hostname>

# 3. Check TCP port reachability (SSH / Agent port)
nc -zv -w 3 <target_ip_or_hostname> 22
nc -zv -w 3 <target_ip_or_hostname> 5665
```

### Root Cause Analysis (RCA):
- **Network Routing / Gateway Failure:** Core switch or default gateway is unreachable; check if multiple hosts on the same subnet are down simultaneously.
- **Firewall / Security Group Blocking:** Recent iptables, ufw, or cloud security group rule change dropped ICMP or monitoring port 5665.
- **Server Kernel Crash / Hardware Outage:** Target hypervisor or physical server halted, kernel panicked, or lost power.
- **Scheduled Maintenance:** Host was taken offline for maintenance without scheduling a downtime in Icinga.

### Remediation Plan:
1. If all hosts in a zone are DOWN, investigate the upstream network switch or gateway before troubleshooting individual hosts.
2. If isolated, check IPMI/iLO/vCenter console for hardware or OS kernel panics (`kernel panic - not syncing`).
3. If scheduled maintenance is in progress, schedule a downtime via the AI Agent: `schedule_host_downtime(hostname="<host>", duration_hours=2.0, comment="Maintenance")`.
4. Trigger an immediate check once resolved: `force_recheck(hostname="<host>")`.

---

## 2. Alert: Disk Space Full / Filesystem Read-Only / Inode Depletion
**Symptom / Trigger:** `check_disk` returns `CRITICAL - / is 98% full (free: 1.2 GB)` or `DISK CRITICAL - /var/log free space: 0 MB` or `exit code 2`.

### Diagnostic Commands:
```bash
# 1. Check disk utilization and inode availability
df -h
df -i

# 2. Identify top space-consuming directories
du -ahx / 2>/dev/null | sort -rh | head -n 20
du -sh /var/log/* 2>/dev/null | sort -rh | head -n 10

# 3. Check for open unlinked files held by deleted processes
lsof +L1
```

### Root Cause Analysis (RCA):
- **Log Bloat:** Runaway application logging or uncompressed rotated logs in `/var/log` (e.g., `syslog`, `journal`, `/var/log/icinga2/icinga2.log`).
- **Core Dumps / Crash Reports:** Application crashes generating multi-gigabyte coredump files in `/var/lib/systemd/coredump/` or `/tmp`.
- **Docker Container Build / Volume Accumulation:** Unused dangling images, exited containers, and build cache in `/var/lib/docker`.
- **Inode Depletion:** Millions of tiny session or spool files (e.g. `/var/spool/postfix` or `/tmp`) consuming all inodes even if disk GB remains.
- **Deleted File Held by Process:** Log file deleted with `rm` but process still has file descriptor open (`lsof +L1`), holding disk blocks.

### Remediation Plan:
1. **Vacuum systemd logs:**
   ```bash
   journalctl --vacuum-time=2d --vacuum-size=500M
   ```
2. **Clean package cache and temp files:**
   ```bash
   apt-get clean || yum clean all
   rm -rf /tmp/*.tmp /var/tmp/*.tmp
   ```
3. **Prune Docker dangling assets:**
   ```bash
   docker system prune -af --volumes
   ```
4. **Restart process holding deleted files:**
   ```bash
   systemctl restart <service_holding_deleted_file>
   ```
5. Verify disk status with `force_recheck(hostname="<host>", service="disk /")`.

---

## 3. Alert: High CPU Load & Runaway Process Spikes
**Symptom / Trigger:** `check_load` returns `CRITICAL - load average: 28.5, 24.1, 19.8` or `CPU utilization > 95%`.

### Diagnostic Commands:
```bash
# 1. Real-time process and CPU breakdown
top -b -n 1 | head -n 25
htop

# 2. Check I/O wait vs pure user CPU
vmstat 1 5
iostat -xz 1 5

# 3. Identify top CPU consuming processes
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -n 15
```

### Root Cause Analysis (RCA):
- **Runaway Application Loop:** Buggy worker thread spinning at 100% CPU.
- **High I/O Wait (`wa%` in top):** Slow disk subsystem or saturated storage causing CPU processes to queue in uninterruptible sleep (`D` state).
- **Configuration Deployment Surge:** Icinga Director or Ansible deploying large configurations simultaneously across all nodes.
- **Crypto-mining or Unauthorized Process:** Malicious process running from `/tmp` or unprivileged user account.

### Remediation Plan:
1. Check if high load is caused by `wa%` (disk bottleneck) or `us%` (application processing).
2. If a specific background job is runaway:
   ```bash
   kill -15 <PID>   # Graceful termination
   kill -9 <PID>    # Force kill if unresponsive
   ```
3. If Icinga 2 checker is saturated, balance check distribution across satellite zones or increase `concurrent_checks` in `icinga2.conf`.

---

## 4. Alert: High Memory Usage & Linux Kernel OOM Killer
**Symptom / Trigger:** `check_mem` returns `CRITICAL - Memory usage: 97%` or application suddenly terminates with exit code 137 (OOM killed).

### Diagnostic Commands:
```bash
# 1. Inspect memory and swap usage
free -m
cat /proc/meminfo | head -n 20

# 2. Check kernel logs for Out Of Memory (OOM) killer events
dmesg -T | grep -i -E "oom|out of memory|killed process"
journalctl -k --grep="Out of memory" -n 20

# 3. Identify top memory consumers
ps -eo pid,user,rss,%mem,command --sort=-rss | head -n 15
```

### Root Cause Analysis (RCA):
- **Memory Leak:** Application fails to free heap objects over time.
- **JVM Heap Exhaustion:** Java application (Elasticsearch/Logstash/Kafka) exceeded `-Xmx` limits.
- **Buffer / Cache Misinterpretation:** Linux aggressively caches disk reads into RAM. Look at `available` RAM in `free -m`, not `free`.
- **Disabled Swap:** Systems with 0 swap space trigger OOM killer immediately upon memory pressure spikes.

### Remediation Plan:
1. Restart the memory-leaking service: `systemctl restart <service_name>`.
2. Tune application max heap limits (e.g. `ES_JAVA_OPTS="-Xms4g -Xmx4g"` for Elasticsearch).
3. If transient, drop Linux filesystem cache safely:
   ```bash
   sync; echo 3 > /proc/sys/vm/drop_caches
   ```
4. Acknowledge alert and monitor memory curve: `acknowledge_alert(hostname="<host>", comment="Memory leak investigated, service restarted")`.

---

## 5. Alert: MySQL / IDO Database Degradation & Connection Spikes
**Symptom / Trigger:** `check_mysql` returns `CRITICAL - Can't connect to MySQL server` or `Too many connections` or `IDO database query latency > 5s`.

### Diagnostic Commands:
```bash
# 1. Check MySQL service and active processlist
systemctl status mysql || systemctl status mariadb
mysql -u root -p -e "SHOW FULL PROCESSLIST;"
mysql -u root -p -e "SHOW GLOBAL STATUS LIKE 'Threads_connected';"
mysql -u root -p -e "SHOW VARIABLES LIKE 'max_connections';"

# 2. Check slow query log and InnoDB status
mysql -u root -p -e "SHOW ENGINE INNODB STATUS\G"
tail -n 50 /var/log/mysql/slow.log
```

### Root Cause Analysis (RCA):
- **Max Connections Exhausted:** Spikes in web client requests or leaked database pool connections.
- **Long-Running Table Lock / Deadlock:** Heavy reporting queries blocking Icinga IDO write operations.
- **Disk Space Full on Database Volume:** MySQL binary logs (`binlog`) filled `/var/lib/mysql`.

### Remediation Plan:
1. Kill blocking long-running sleep queries:
   ```sql
   KILL <thread_id>;
   ```
2. Increase max connections dynamically:
   ```sql
   SET GLOBAL max_connections = 500;
   ```
3. Purge old binary logs if disk space is low:
   ```sql
   PURGE BINARY LOGS BEFORE DATE_SUB(NOW(), INTERVAL 3 DAY);
   ```
4. Restart MySQL if completely locked: `systemctl restart mysql`.

---

## 6. Alert: Web Server & Reverse Proxy Errors (Nginx / Apache / 502 / 504)
**Symptom / Trigger:** `check_http` returns `CRITICAL - HTTP/1.1 502 Bad Gateway` or `HTTP/1.1 504 Gateway Timeout` or `Connection refused`.

### Diagnostic Commands:
```bash
# 1. Check web server and upstream backend status
systemctl status nginx || systemctl status apache2
systemctl status php8.2-fpm || systemctl status php-fpm

# 2. Inspect Nginx error logs
tail -n 50 /var/log/nginx/error.log
grep -i -E "upstream|connect() failed|timed out" /var/log/nginx/error.log | tail -n 20

# 3. Test backend socket/port response
curl -I http://127.0.0.1:8000/api/health
```

### Root Cause Analysis (RCA):
- **502 Bad Gateway:** Upstream application (FastAPI / PHP-FPM / Node.js) crashed or is not listening on the expected Unix socket/port.
- **504 Gateway Timeout:** Upstream application is alive but taking longer to respond than `proxy_read_timeout` (e.g. heavy query or blocked thread).
- **Socket Permissions:** Nginx cannot read `/var/run/php/php-fpm.sock` due to permissions.

### Remediation Plan:
1. Restart the upstream application server:
   ```bash
   systemctl restart php8.2-fpm || systemctl restart icinga-ai-api
   ```
2. Test Nginx configuration and reload:
   ```bash
   nginx -t && systemctl reload nginx
   ```
3. If requests are timing out, increase proxy timeout in `/etc/nginx/nginx.conf`:
   ```nginx
   proxy_read_timeout 300s;
   proxy_connect_timeout 75s;
   ```

---

## 7. Alert: SSL / TLS Certificate Expiry
**Symptom / Trigger:** `check_ssl_cert` returns `WARNING - Certificate expires in 14 days` or `CRITICAL - Certificate expired on ...`.

### Diagnostic Commands:
```bash
# 1. Inspect certificate expiration date
echo | openssl s_client -servername <domain> -connect <host>:443 2>/dev/null | openssl x509 -noout -dates

# 2. Check Certbot renewal timers
certbot certificates
systemctl status certbot.timer
```

### Remediation Plan:
1. Trigger manual Certbot renewal:
   ```bash
   certbot renew --dry-run
   certbot renew --force-renewal
   ```
2. Reload web server to load new certificates: `systemctl reload nginx`.

---

## 8. Alert: Icinga 2 Satellite Node Sync & Check Latency
**Symptom / Trigger:** Satellite node reports `Check latency > 15 seconds` or `Zone endpoint is not connected` or checks remain in PENDING state.

### Diagnostic Commands:
```bash
# 1. Check Icinga 2 daemon status and logs on satellite
systemctl status icinga2
tail -n 100 /var/log/icinga2/icinga2.log | grep -i -E "error|warning|cluster"

# 2. Check TLS certificate validity between Master and Satellite
icinga2 pki verify --cert /var/lib/icinga2/certs/<node>.crt --cacert /var/lib/icinga2/certs/ca.crt

# 3. Test port 5665 connectivity to Master
nc -zv -w 5 <master_ip> 5665
```

### Root Cause Analysis (RCA):
- **TLS Certificate Mismatch / Expiry:** Satellite PKI cert expired or does not match Master CA.
- **Port 5665 Blocked:** Firewall dropped connection between Master and Satellite zone.
- **Clock Drift:** Master and Satellite system clocks are out of sync by > 10 seconds.

### Remediation Plan:
1. Sync system time using NTP/chrony: `chronyc -a makestep || ntpdate pool.ntp.org`.
2. If PKI mismatch, regenerate satellite ticket and re-run node setup:
   ```bash
   icinga2 node setup --ticket <ticket> --endpoint <master> --zone <zone>
   systemctl restart icinga2
   ```

---

## 9. Alert: Elasticsearch / OpenSearch Red Cluster & Unassigned Shards
**Symptom / Trigger:** `get_elasticsearch_cluster_health()` returns `status: red` or `status: yellow` or `unassigned_shards > 0`.

### Diagnostic Commands:
```bash
# 1. Check cluster health and explain unassigned shards
curl -s http://localhost:9200/_cluster/health?pretty
curl -s http://localhost:9200/_cat/shards?v | grep -i UNASSIGNED
curl -s http://localhost:9200/_cluster/allocation/explain?pretty
```

### Root Cause Analysis (RCA):
- **Disk Flood-Stage Watermark Breached (>95%):** OpenSearch automatically locks indices into `read_only_allow_delete` mode when disk usage exceeds 95%.
- **Node Drop:** A node holding primary shards went offline.
- **Corrupt Lucene Index:** Index segment corruption following an unclean server shutdown.

### Remediation Plan:
1. Clear disk space on the OpenSearch host to drop below 85% disk usage.
2. Release the flood-stage index read-only lock:
   ```bash
   curl -X PUT "http://localhost:9200/_all/_settings" -H 'Content-Type: application/json' -d'{"index.blocks.read_only_allow_delete": null}'
   ```
3. Trigger shard re-allocation:
   ```bash
   curl -X POST "http://localhost:9200/_cluster/reroute?retry_failed=true"
   ```

---

## 10. Alert: Docker Container / Service Crashes (CrashLoopBackOff)
**Symptom / Trigger:** `check_docker` returns `CRITICAL - Container <name> exited with status 137 / 1`.

### Diagnostic Commands:
```bash
# 1. Inspect container status and exit code
docker ps -a --filter "status=exited"
docker inspect <container_id> --format='{{.State.ExitCode}} {{.State.Error}}'

# 2. View recent container crash logs
docker logs --tail 100 <container_id>
```

### Root Cause Analysis (RCA):
- **Exit Code 137:** Container was killed by Linux OOM killer (exceeded Docker memory limit).
- **Exit Code 1:** Application fatal runtime exception or missing environment variable.
- **Port Conflict (Address already in use):** Another process bound the host port before the container started.

### Remediation Plan:
1. Restart container with increased memory limits in `docker-compose.yaml`.
2. Inspect logs and restart container: `docker restart <container_name>`.
3. Force recheck in Icinga to clear alert: `force_recheck(hostname="<host>")`.

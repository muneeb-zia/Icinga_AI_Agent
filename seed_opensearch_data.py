from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk
from datetime import datetime, timedelta
import random

client = OpenSearch([{"host": "localhost", "port": 9200, "scheme": "http"}])

index_name = f"icinga2-{datetime.utcnow().strftime('%Y.%m.%d')}"
try:
    client.indices.create(index=index_name)
except Exception as e:
    print(f"Index creation note: {e}")

now = datetime.utcnow()
docs = []

print("Generating mock data for CPU and logs...")
for i in range(24 * 60): # Every minute for the last 24 hours
    ts = now - timedelta(minutes=i)
    
    # CPU usage: normally 10-30%, but a massive spike 2-4 hours ago
    if 120 <= i <= 240:
        cpu_val = random.uniform(85.0, 99.0)
    else:
        cpu_val = random.uniform(10.0, 30.0)
        
    docs.append({
        "@timestamp": ts.isoformat() + "Z",
        "host": "icinga-master",
        "label": "cpu",
        "value": cpu_val
    })
    
    # Log volume: normally 1-5 logs/min, but spike 2-4 hours ago to 30-50 logs/min
    num_logs = random.randint(1, 5)
    if 120 <= i <= 240:
        num_logs = random.randint(30, 50)
        
    for _ in range(num_logs):
        docs.append({
            "@timestamp": ts.isoformat() + "Z",
            "host": "icinga-master",
            "message": "Mock log message for testing visualizations.",
            "output": "Mock output",
            "type": "log"
        })

print(f"Inserting {len(docs)} documents...")
bulk_data = [{"_index": index_name, "_source": d} for d in docs]
bulk(client, bulk_data)
print("Data seeded successfully!")

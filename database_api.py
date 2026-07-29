import mysql.connector
from typing import List, Dict

DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_USER = "icinga2"
DB_PASS = "mCX6B32ZO6DdAzq"
DB_NAME = "icinga2idomysql"

def _get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )

def get_historical_outages(hostname: str, limit: int = 5) -> Dict:
    """
    Fetches the historical state changes (like when it went DOWN or CRITICAL) 
    for a specific host from the Icinga Database.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Find the object_id for the host
        cursor.execute("SELECT object_id FROM icinga_objects WHERE name1 = %s AND objecttype_id = 1 LIMIT 1;", (hostname,))
        obj = cursor.fetchone()
        
        if not obj:
            return {"error": f"Host '{hostname}' not found in database."}
            
        object_id = obj['object_id']
        
        # 2. Fetch the state history where state != 0 (0 is UP/OK)
        query = """
            SELECT state_time, state, output 
            FROM icinga_statehistory 
            WHERE object_id = %s AND state != 0 
            ORDER BY state_time DESC 
            LIMIT %s;
        """
        cursor.execute(query, (object_id, limit))
        history = cursor.fetchall()
        
        # Convert datetime to string
        for row in history:
            row['state_time'] = str(row['state_time'])
            
        return {
            "host": hostname,
            "historical_outages": history,
            "total_found": len(history)
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def get_recent_downtimes(limit: int = 5) -> Dict:
    """
    Fetches a list of the most recent scheduled downtimes from the database.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT author_name, comment_data, scheduled_start_time, scheduled_end_time 
            FROM icinga_downtimehistory 
            ORDER BY scheduled_start_time DESC 
            LIMIT %s;
        """
        cursor.execute(query, (limit,))
        downtimes = cursor.fetchall()
        
        for row in downtimes:
            row['scheduled_start_time'] = str(row['scheduled_start_time'])
            row['scheduled_end_time'] = str(row['scheduled_end_time'])
            
        return {
            "recent_downtimes": downtimes,
            "total_found": len(downtimes)
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    print(get_historical_outages("icinga-master"))
    print(get_recent_downtimes())

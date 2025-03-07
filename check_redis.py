import redis

# Redis connection details
REDIS_HOST = "redis-12510.c84.us-east-1-2.ec2.redns.redis-cloud.com"
REDIS_PORT = 12510
REDIS_PASSWORD = "OTDCIhUjS5RBTLskLwoUYjPQXbFDBMHt"

def try_connection(use_ssl=True):
    try:
        # Connect to Redis
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            username="default",
            decode_responses=True,
            ssl=use_ssl
        )
        
        # Test connection
        print(f"\nTesting {'SSL' if use_ssl else 'non-SSL'} connection...")
        print("PING test:", r.ping())
        print("Setting test value...")
        r.set("test_key", "test_value")
        print("Getting test value:", r.get("test_key"))
        return True
        
    except Exception as e:
        print(f"Error with {'SSL' if use_ssl else 'non-SSL'} connection: {str(e)}")
        return False

# Try SSL first
if not try_connection(use_ssl=True):
    print("\nTrying non-SSL connection...")
    try_connection(use_ssl=False) 
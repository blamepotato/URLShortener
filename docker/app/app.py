from flask import Flask, request, redirect
import redis
from cassandra.cluster import Cluster, ExecutionProfile, EXEC_PROFILE_DEFAULT
import cassandra.policies as cp
import cassandra.query as cq
from cassandra import ConsistencyLevel


app = Flask(__name__)

# Configure Redis connection
cache = redis.Redis(host='redis-primary', db=0, port=6379, decode_responses=True)

profile = ExecutionProfile(
	load_balancing_policy=cp.WhiteListRoundRobinPolicy(['127.0.0.1']),
	retry_policy=cp.DowngradingConsistencyRetryPolicy(),
	consistency_level=ConsistencyLevel.LOCAL_QUORUM,
	serial_consistency_level=ConsistencyLevel.LOCAL_SERIAL,
	request_timeout=15,
	row_factory=cq.tuple_factory
)

cluster = Cluster(execution_profiles={EXEC_PROFILE_DEFAULT: profile})
# Configure Cassandra connection
cluster = Cluster(['10.128.1.70', '10.128.2.70', '10.128.3.70'])
session = cluster.connect('urlshortener')

@app.route('/', methods=['PUT'])
def long_to_short():
    shorturl = request.args['short']
    longurl = request.args.args['long']
    # returns 400 if either short or long is not provided
    if not shorturl or not longurl:
        return 'Bad request', 400
    # Store in Cassandra
    session.execute("INSERT INTO urls (shorturl, longurl) VALUES (%s, %s)", (shorturl, longurl))
    # Store in Redis
    cache.set(shorturl, longurl)
    return 'OK', 200

@app.route('/<shorturl>', methods=['GET'])
def short_to_long(shorturl):
    # returns 400 if shorturl is not provided
    if not shorturl.strip():
        return 'Bad request', 400
    # Try to get the long URL from Redis cache
    longurl = cache.get(shorturl)
    if longurl:
        return redirect(longurl, code=307)
    else:
        # If not found in Redis, get it from Cassandra
        row = session.execute("SELECT longurl FROM urls WHERE shorturl = %s", (shorturl,)).one()
        if row:
            cache.set(shorturl, row.longurl)
            return redirect(row.longurl, code=307)
        return 'page not found', 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)

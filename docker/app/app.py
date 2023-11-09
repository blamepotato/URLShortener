from flask import Flask, request, redirect
import redis
from cassandra.cluster import Cluster

app = Flask(__name__)

# Configure Redis connection
cache = redis.Redis(host='redis-primary', db=0, port=6379, decode_responses=True)

# Configure Cassandra connection
cluster = Cluster(['10.128.1.70', '10.128.2.70', '10.128.3.70'])
session = cluster.connect('urlshortener')

@app.route('/', methods=['PUT'])
def long_to_short():
    shorturl = request.args['short']
    longurl = request.args['long']
    # returns 400 if either short or long is not provided
    if not shorturl or not longurl:
        return 'bad request', 400
    # Store in Cassandra
    session.execute("INSERT INTO urls (shorturl, longurl) VALUES (%s, %s)", (shorturl, longurl))
    # Store in Redis
    cache.set(shorturl, longurl)
    return 'OK', 200

@app.route('/<shorturl>', methods=['GET'])
def short_to_long(shorturl):
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
    
# Catch-all route for bad requests to the root that don't match the 'good' request format.
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['GET'])
def catch_all(path):
    # Since this is a catch-all, it will capture all requests not previously matched.
    # If it's a GET request to the root or any other path not matching the 'good' format, return 400.
    return 'bad request', 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)

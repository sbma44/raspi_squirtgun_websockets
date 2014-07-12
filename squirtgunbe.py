# -*- coding: utf-8 -*-

"""
Chat Server
===========

This simple application uses WebSockets to run a primitive chat server.
"""

import os
import logging
import redis
import gevent
import json
import time
from functools import wraps
from flask import Flask, render_template, request, Response
from flask_sockets import Sockets

REDIS_URL = os.environ['REDISCLOUD_URL']
REDIS_CHAN = 'chat'

KEEPALIVE_TIMEOUT = 15

app = Flask(__name__)
app.debug = 'DEBUG' in os.environ

sockets = Sockets(app)
redis = redis.from_url(REDIS_URL)

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == 'admin' and password == 'secret'

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


class SquirtgunBackend(object):
    """Interface for registering and updating WebSocket clients."""

    def __init__(self):
        self.clients = list()
        self.pubsub = redis.pubsub()
        self.pubsub.subscribe(REDIS_CHAN)

    def __iter_data(self):
        for message in self.pubsub.listen():
            data = message.get('data')
            if message['type'] == 'message':
                app.logger.info(u'Sending message: {}'.format(data))
                yield data

    def register(self, client):
        """Register a WebSocket connection for Redis updates."""
        self.clients.append(client)

    def send(self, client, data):
        """Send given data to the registered client.
        Automatically discards invalid connections."""
        try:
            client.send(data)
        except Exception:
            self.clients.remove(client)

    def run(self):
        """Listens for new messages in Redis, and sends them to clients."""
        for data in self.__iter_data():
            for client in self.clients:
                gevent.spawn(self.send, client, data)

    def start(self):
        """Maintains Redis subscription in the background."""
        gevent.spawn(self.run)

chats = SquirtgunBackend()
chats.start()


@app.route('/')
def hello():
    return render_template('index.html')

# @app.route('/client-list')
# def client_list():
#     peers = list()
#     for c in chats.clients:
#         peers.append(":".join(map(lambda x: str(x), c.socket.getpeername())))
#     return json.dumps({'peers': peers})

@app.route('/client-count')
def client_list():
    keepalive = json.loads(redis.get('keepalive'))
    for (client, last_observation) in keepalive.items():
        if time.time() - last_observation > KEEPALIVE_TIMEOUT:
            del keepalive[client]
    redis.set('keepalive', json.dumps(keepalive))
    return json.dumps({'client_count': len(keepalive)})

@sockets.route('/submit')
def inbox(ws):
    """Receives incoming chat messages, inserts them into Redis."""
    while ws.socket is not None:
        # Sleep to prevent *constant* context-switches.
        gevent.sleep(0.1)
        message = ws.receive()

        if message:
            try:
                message_json = json.loads(message)
                if message_json.has_key('keepalive'):
                    keepalive = dict()
                    keepalive[message_json['keepalive']] = time.time()
                    redis.set('keepalive', json.dumps(keepalive))
                else:
                    app.logger.info(u'Inserting message: {}'.format(message))
                    redis.publish(REDIS_CHAN, message)
            except:
                continue
            

@sockets.route('/receive')
def outbox(ws):
    """Sends outgoing chat messages, via `SquirtgunBackend`."""
    chats.register(ws)

    while ws.socket is not None:
        # Context switch while `SquirtgunBackend.start` is running in the background.
        gevent.sleep()




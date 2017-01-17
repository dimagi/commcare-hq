"""
A collection of functions which test the most basic operations of various services.
"""
from collections import namedtuple
import datetime
import json
import logging
from StringIO import StringIO
import time

from django.core import cache
from django.conf import settings
from django.contrib.auth.models import User
from restkit import Resource
from celery import Celery
import requests
from soil import heartbeat

from corehq.apps.nimbus_api.utils import get_nimbus_url
from corehq.apps.app_manager.models import Application
from corehq.apps.change_feed.connection import get_kafka_client_or_none
from corehq.apps.es import GroupES
from corehq.blobs import get_blob_db
from corehq.blobs.util import random_url_id
from corehq.elastic import send_to_elasticsearch
from corehq.util.decorators import change_log_level
from corehq.apps.hqadmin.utils import parse_celery_workers, parse_celery_pings

ServiceStatus = namedtuple("ServiceStatus", "success msg")


def check_redis():
    if 'redis' in settings.CACHES:
        import redis
        rc = cache.caches['redis']
        redis_api = redis.StrictRedis.from_url('%s' % rc._server)
        memory = redis_api.info()['used_memory_human']
        result = rc.set('serverup_check_key', 'test', timeout=5)
        return ServiceStatus(result, "Redis is up and using {} memory".format(memory))
    else:
        return ServiceStatus(False, "Redis is not configured on this system!")


def check_rabbitmq():
    if settings.BROKER_URL.startswith('amqp'):
        amqp_parts = settings.BROKER_URL.replace('amqp://', '').split('/')
        mq_management_url = amqp_parts[0].replace('5672', '15672')
        vhost = amqp_parts[1]
        try:
            mq = Resource('http://%s' % mq_management_url, timeout=2)
            vhost_dict = json.loads(mq.get('api/vhosts', timeout=2).body_string())
            for d in vhost_dict:
                if d['name'] == vhost:
                    return ServiceStatus(True, 'RabbitMQ OK')
            return ServiceStatus(False, 'RabbitMQ Offline')
        except Exception as e:
            return ServiceStatus(False, "RabbitMQ Error: %s" % e)
    else:
        return ServiceStatus(False, "RabbitMQ Not configured")


@change_log_level('kafka.client', logging.WARNING)
def check_kafka():
    client = get_kafka_client_or_none()
    if not client:
        return ServiceStatus(False, "Could not connect to Kafka")
    elif len(client.brokers) == 0:
        return ServiceStatus(False, "No Kafka brokers found")
    elif len(client.topics) == 0:
        return ServiceStatus(False, "No Kafka topics found")
    else:
        return ServiceStatus(True, "Kafka seems to be in order")


def check_touchforms():
    try:
        res = requests.post(settings.XFORMS_PLAYER_URL,
                            data='{"action": "heartbeat"}',
                            timeout=5)
    except requests.exceptions.ConnectTimeout:
        return ServiceStatus(False, "Could not establish a connection in time")
    except requests.ConnectionError:
        return ServiceStatus(False, "Could not connect to touchforms")
    else:
        msg = "Touchforms returned a {} status code".format(res.status_code)
        return ServiceStatus(res.ok, msg)


@change_log_level('urllib3.connectionpool', logging.WARNING)
def check_elasticsearch():
    doc = {'_id': 'elasticsearch-service-check',
           'date': datetime.datetime.now().isoformat()}
    send_to_elasticsearch('groups', doc)
    time.sleep(1)
    hits = GroupES().remove_default_filters().doc_id(doc['_id']).run().hits
    send_to_elasticsearch('groups', doc, delete=True)  # clean up
    if doc in hits:
        return ServiceStatus(True, "Successfully sent a doc to ES and read it back")
    return ServiceStatus(False, "Something went wrong sending a doc to ES")


def check_blobdb():
    """Save something to the blobdb and try reading it back."""
    db = get_blob_db()
    contents = "It takes Pluto 248 Earth years to complete one orbit!"
    info = db.put(StringIO(contents), random_url_id(16))
    with db.get(info.identifier) as fh:
        res = fh.read()
    db.delete(info.identifier)
    if res == contents:
        return ServiceStatus(True, "Successfully saved a file to the blobdb")
    return ServiceStatus(False, "Failed to save a file to the blobdb")


def check_celery():
    from celery import Celery
    from django.conf import settings
    celery = Celery()
    celery.config_from_object(settings)
    worker_responses = celery.control.ping(timeout=10)
    if not worker_responses:
        return ServiceStatus(False, 'No running Celery workers were found.')
    else:
        msg = 'Successfully pinged {} workers'.format(len(worker_responses))
        return ServiceStatus(True, msg)


def check_heartbeat():
    celery_monitoring = getattr(settings, 'CELERY_FLOWER_URL', None)
    if celery_monitoring:
        cresource = Resource(celery_monitoring, timeout=3)
        t = cresource.get("api/workers", params_dict={'status': True}).body_string()
        all_workers = json.loads(t)
        bad_workers = []
        expected_running, expected_stopped = parse_celery_workers(all_workers)

        celery = Celery()
        celery.config_from_object(settings)
        worker_responses = celery.control.ping(timeout=10)
        pings = parse_celery_pings(worker_responses)

        for hostname in expected_running:
            if hostname not in pings or not pings[hostname]:
                bad_workers.append('* {} celery worker down'.format(hostname))

        for hostname in expected_stopped:
            if hostname in pings:
                bad_workers.append(
                    '* {} celery worker is running when we expect it to be stopped.'.format(hostname)
                )

        if bad_workers:
            return ServiceStatus(False, '\n'.join(bad_workers))

    is_alive = heartbeat.is_alive()
    return ServiceStatus(is_alive, "OK" if is_alive else "DOWN")


def check_postgres():
    a_user = User.objects.first()
    if a_user is None:
        return ServiceStatus(False, "No users found in postgres")
    return ServiceStatus(True, "Successfully got a user from postgres")


def check_couch():
    """Confirm CouchDB is up and running, by hitting an arbitrary view."""
    results = Application.view('app_manager/builds_by_date', limit=1).all()
    assert isinstance(results, list), "Couch didn't return a list of builds"
    return ServiceStatus(True, "Successfully queried an arbitrary couch view")


def check_formplayer():
    try:
        res = requests.get('{}/serverup'.format(get_nimbus_url()), timeout=5)
    except requests.exceptions.ConnectTimeout:
        return ServiceStatus(False, "Could not establish a connection in time")
    except requests.ConnectionError:
        return ServiceStatus(False, "Could not connect to formplayer")
    else:
        msg = "Formplayer returned a {} status code".format(res.status_code)
        return ServiceStatus(res.ok, msg)


CHECKS = {
    'kafka': check_kafka,
    'redis': check_redis,
    'postgres': check_postgres,
    'couch': check_couch,
    'celery': check_celery,
    'heartbeat': check_heartbeat,
    'touchforms': check_touchforms,
    'elasticsearch': check_elasticsearch,
    'blobdb': check_blobdb,
    'formplayer': check_formplayer,
}

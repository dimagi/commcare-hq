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
import requests
from soil import heartbeat
from dimagi.utils.web import get_url_base

from corehq.apps.app_manager.models import Application
from corehq.apps.change_feed.connection import get_kafka_client_or_none
from corehq.apps.es import GroupES
from corehq.blobs import get_blob_db
from corehq.elastic import send_to_elasticsearch
from corehq.util.decorators import change_log_level
from corehq.apps.hqadmin.utils import parse_celery_workers

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


def check_pillowtop():
    return ServiceStatus(False, "Not implemented")


@change_log_level('kafka.client', logging.WARNING)
def check_kafka():
    client = get_kafka_client_or_none()
    if not client:
        return ServiceStatus(False, "Could not connect to Kafka")
    # TODO elaborate?
    return ServiceStatus(True, "Kafka's fine. Probably.")


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


def check_shared_dir():
    return ServiceStatus(False, "Not implemented")


def check_blobdb():
    """Save something to the blobdb and try reading it back."""
    db = get_blob_db()
    contents = "It takes Pluto 248 Earth years to complete one orbit!"
    info = db.put(StringIO(contents))
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

        for hostname in expected_running:
            if not all_workers[hostname]:
                bad_workers.append('* {} celery worker down'.format(hostname))

        for hostname in expected_stopped:
            if all_workers[hostname]:
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
    formplayer_url = settings.FORMPLAYER_URL
    if not formplayer_url.startswith('http'):
        formplayer_url = '{}{}'.format(get_url_base(), formplayer_url)

    try:
        res = requests.get('{}/serverup'.format(formplayer_url), timeout=5)
    except requests.exceptions.ConnectTimeout:
        return ServiceStatus(False, "Could not establish a connection in time")
    except requests.ConnectionError:
        return ServiceStatus(False, "Could not connect to formplayer")
    else:
        msg = "Formplayer returned a {} status code".format(res.status_code)
        return ServiceStatus(res.ok, msg)


checks = (
    check_pillowtop,
    check_kafka,
    check_redis,
    check_postgres,
    check_couch,
    check_celery,
    check_heartbeat,
    check_touchforms,
    check_elasticsearch,
    check_shared_dir,
    check_blobdb,
    check_formplayer,
)

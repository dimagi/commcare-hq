"""
A collection of functions which test the most basic operations of various services.
"""

import datetime
import logging
import re
import time
import uuid
from io import BytesIO

from django.conf import settings
from django.contrib.auth.models import User
from django.core import cache
from django.db import connections
from django.db.utils import OperationalError

import attr
import gevent
import requests
from celery import Celery

from pillowtop.utils import get_all_pillow_instances
from pillowtop.checkpoints.manager import MAX_CHECKPOINT_DELAY
from soil import heartbeat

from corehq.apps.app_manager.models import Application
from corehq.apps.change_feed.connection import get_kafka_client
from corehq.apps.es import GroupES
from corehq.apps.formplayer_api.utils import get_formplayer_url
from corehq.apps.hqadmin.escheck import check_es_cluster_health
from corehq.apps.hqadmin.utils import parse_celery_pings, parse_celery_workers
from corehq.blobs import CODES, get_blob_db
from corehq.celery_monitoring.heartbeat import (
    Heartbeat,
    HeartbeatNeverRecorded,
)
from corehq.elastic import refresh_elasticsearch_index, send_to_elasticsearch
from corehq.util.decorators import change_log_level
from corehq.util.timer import TimingContext


@attr.s
class ServiceStatus(object):
    success = attr.ib()
    msg = attr.ib()
    exception = attr.ib(default=None)
    duration = attr.ib(default=None)


class UnknownCheckException(Exception):
    pass


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


def check_all_rabbitmq():
    unwell_rabbits = []
    ip_regex = re.compile(r'[0-9]+.[0-9]+.[0-9]+.[0-9]+')

    for broker_url in settings.BROKER_URL.split(';'):
        check_status, failure = check_rabbitmq(broker_url)
        if not check_status:
            failed_rabbit_ip = ip_regex.search(broker_url).group()
            unwell_rabbits.append((failed_rabbit_ip, failure))

    if not unwell_rabbits:
        return ServiceStatus(True, 'RabbitMQ OK')

    else:
        return ServiceStatus(False, '; '.join(['{}:{}'.format(rabbit[0], rabbit[1])
                                        for rabbit in unwell_rabbits])
                      )


def check_rabbitmq(broker_url):
    if broker_url.startswith('amqp'):
        amqp_parts = broker_url.replace('amqp://', '').split('/')
        mq_management_url = amqp_parts[0].replace('5672', '15672')
        vhost = amqp_parts[1]
        try:
            vhost_dict = requests.get('http://%s/api/vhosts' % mq_management_url, timeout=2).json()
            for d in vhost_dict:
                if d['name'] == vhost:
                    return True, 'RabbitMQ OK'
            return False, 'RabbitMQ Offline'
        except Exception as e:
            return False, "RabbitMQ Error: %s" % e
    elif settings.BROKER_URL.startswith('redis'):
        return True, "RabbitMQ Not configured, but not needed"
    else:
        return False, "RabbitMQ Not configured"


@change_log_level('kafka.client', logging.WARNING)
def check_kafka():
    try:
        client = get_kafka_client()
    except Exception as e:
        return ServiceStatus(False, "Could not connect to Kafka: %s" % e)

    if len(client.cluster.brokers()) == 0:
        return ServiceStatus(False, "No Kafka brokers found")
    elif len(client.cluster.topics()) == 0:
        return ServiceStatus(False, "No Kafka topics found")
    else:
        return ServiceStatus(True, "Kafka seems to be in order")


@change_log_level('urllib3.connectionpool', logging.WARNING)
def check_elasticsearch():
    cluster_health = check_es_cluster_health()
    if cluster_health == 'red':
        return ServiceStatus(False, "Cluster health at %s" % cluster_health)

    doc = {'_id': 'elasticsearch-service-check-{}'.format(uuid.uuid4().hex[:7]),
           'date': datetime.datetime.now().isoformat()}
    try:
        send_to_elasticsearch('groups', doc)
        refresh_elasticsearch_index('groups')
        hits = GroupES().remove_default_filters().doc_id(doc['_id']).run().hits
        if doc in hits:
            return ServiceStatus(True, "Successfully sent a doc to ES and read it back")
        else:
            return ServiceStatus(False, "Something went wrong sending a doc to ES")
    finally:
        send_to_elasticsearch('groups', doc, delete=True)  # clean up


def check_blobdb():
    """Save something to the blobdb and try reading it back."""
    db = get_blob_db()
    contents = b"It takes Pluto 248 Earth years to complete one orbit!"
    meta = db.put(
        BytesIO(contents),
        domain="<unknown>",
        parent_id="check_blobdb",
        type_code=CODES.tempfile,
    )
    with db.get(key=meta.key) as fh:
        res = fh.read()
    db.delete(key=meta.key)
    if res == contents:
        return ServiceStatus(True, "Successfully saved a file to the blobdb")
    return ServiceStatus(False, "Failed to save a file to the blobdb")


def check_celery():
    blocked_queues = []

    for queue, threshold in settings.CELERY_HEARTBEAT_THRESHOLDS.items():
        if threshold:
            threshold = datetime.timedelta(seconds=threshold)
            try:
                blockage_duration = Heartbeat(queue).get_and_report_blockage_duration()
            except HeartbeatNeverRecorded:
                blocked_queues.append((queue, 'as long as we can see', threshold))
            else:
                # We get a lot of self-resolving celery "downtime" under 5 minutes
                # so to make actionable, we never alert on blockage under 5 minutes
                # It is still counted as out of SLA for the celery uptime metric in datadog
                if blockage_duration > max(threshold, datetime.timedelta(minutes=5)):
                    blocked_queues.append((queue, blockage_duration, threshold))

    if blocked_queues:
        return ServiceStatus(False, '\n'.join(
            "{} has been blocked for {} (max allowed is {})".format(
                queue, blockage_duration, threshold
            ) for queue, blockage_duration, threshold in blocked_queues))
    else:
        return ServiceStatus(True, "OK")


def check_heartbeat():
    is_alive = heartbeat.is_alive()
    return ServiceStatus(is_alive, "OK" if is_alive else "DOWN")


def check_postgres():
    connected = True
    status_str = ""
    for db in settings.DATABASES:
        db_conn = connections[db]
        try:
            c = db_conn.cursor()
            c_status = 'OK'
        except OperationalError:
            c_status = 'FAIL'
            connected = False
        status_str += "%s:%s:%s " % (db, settings.DATABASES[db]['NAME'], c_status)

    a_user = User.objects.first()
    if a_user is None:
        status_str += "No users found in postgres"
    else:
        status_str += "Successfully got a user from postgres"

    if a_user is None or not connected:
        return ServiceStatus(False, status_str)
    return ServiceStatus(True, status_str)


def check_couch():
    """Confirm CouchDB is up and running, by hitting an arbitrary view."""
    results = Application.view('app_manager/builds_by_date', limit=1).all()
    assert isinstance(results, list), "Couch didn't return a list of builds"
    return ServiceStatus(True, "Successfully queried an arbitrary couch view")


def check_formplayer():
    try:
        # Setting verify=False in this request keeps this from failing for urls with self-signed certificates.
        # Allowing this because the certificate will always be self-signed in the "provable deploy"
        # bootstrapping test in commcare-cloud.
        res = requests.get('{}/serverup'.format(get_formplayer_url()), timeout=5, verify=False)
    except requests.exceptions.ConnectTimeout:
        return ServiceStatus(False, "Could not establish a connection in time")
    except requests.ConnectionError:
        return ServiceStatus(False, "Could not connect to formplayer")
    else:
        msg = "Formplayer returned a {} status code".format(res.status_code)
        return ServiceStatus(res.ok, msg)


def check_pillows():
    pillows = [
        pillow for pillow in get_all_pillow_instances()
        if pillow in getattr(settings, 'ACTIVE_PILLOW_NAMES', [pillow.pillow_id])
        and isinstance(pillow.get_change_feed(), KafkaChangeFeed)
    ]

    failed_pillows = []
    for pillow in pillows:
        oldest_checkpoint = min(c.last_modified for c in pillow.checkpoint._get_checkpoints())
        time_since_oldest = datetime.utcnow() - oldest_checkpoint

        # allow 60 second buffer since save only occurs after max is exceeded
        # and to account for delay between read and comparison
        if time_since_oldest.seconds > (MAX_CHECKPOINT_DELAY + 60):
            failed_pillows.append(pillow.pillow_id)

    if failed_pillows:
        return ServiceStatus(False, '{} have not checkpointed recently'.format(','.join(failed_pillows)))
    else:
        return ServiceStatus(True, 'All pillows checkpointed recently')


def run_checks(checks_to_do):
    greenlets = []
    with TimingContext() as timer:
        for check_name in checks_to_do:
            if check_name not in CHECKS:
                raise UnknownCheckException(check_name)

            greenlets.append(gevent.spawn(_run_check, check_name, timer))
        gevent.joinall(greenlets)
    return [greenlet.value for greenlet in greenlets]


def _run_check(check_name, timer):
    check_info = CHECKS[check_name]
    with timer(check_name):
        try:
            status = check_info['check_func']()
        except Exception as e:
            status = ServiceStatus(False, "{} raised an error".format(check_name), e)
        status.duration = timer.peek().duration
    return check_name, status


CHECKS = {
    'kafka': {
        "always_check": True,
        "check_func": check_kafka,
    },
    'redis': {
        "always_check": True,
        "check_func": check_redis,
    },
    'postgres': {
        "always_check": True,
        "check_func": check_postgres,
    },
    'couch': {
        "always_check": True,
        "check_func": check_couch,
    },
    'celery': {
        "always_check": False,
        "check_func": check_celery,
    },
    'heartbeat': {
        "always_check": False,
        "check_func": check_heartbeat,
    },
    'elasticsearch': {
        "always_check": True,
        "check_func": check_elasticsearch,
    },
    'blobdb': {
        "always_check": True,
        "check_func": check_blobdb,
    },
    'formplayer': {
        "always_check": True,
        "check_func": check_formplayer,
    },
    'rabbitmq': {
        "always_check": True,
        "check_func": check_all_rabbitmq,
    },
    'pillowtop': {
        "always_check": True,
        "check_func": check_pillows,
    }
}

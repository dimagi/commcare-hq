"""
A collection of functions which test the most basic operations of various services.
"""

import datetime
import logging
import re
import uuid
from io import BytesIO

from django.conf import settings
from django.contrib.auth.models import User
from django.core import cache
from django.db import connections
from django.db.utils import OperationalError

import requests
import urllib3

import attr
import gevent
from corehq.apps.app_manager.models import Application
from corehq.apps.change_feed.connection import (
    get_kafka_client,
    get_kafka_consumer,
)
from corehq.apps.es.groups import group_adapter
from corehq.apps.formplayer_api.utils import get_formplayer_url
from corehq.apps.hqadmin.escheck import check_es_cluster_health
from corehq.blobs import CODES, get_blob_db
from corehq.celery_monitoring.heartbeat import (
    Heartbeat,
    HeartbeatNeverRecorded,
)
from corehq.util.decorators import change_log_level, ignore_warning
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
        if isinstance(rc._server, list):
            redis_server = rc._server[0]
        else:
            redis_server = rc._server
        redis_api = redis.StrictRedis.from_url(redis_server)
        memory = redis_api.info()['used_memory_human']
        result = rc.set('serverup_check_key', 'test', timeout=5)
        return ServiceStatus(result, "Redis is up and using {} memory".format(memory))
    else:
        return ServiceStatus(False, "Redis is not configured on this system!")


def check_all_rabbitmq():
    unwell_rabbits = []
    ip_regex = re.compile(r'[0-9]+.[0-9]+.[0-9]+.[0-9]+')

    for broker_url in settings.CELERY_BROKER_URL.split(';'):
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
    elif settings.CELERY_BROKER_URL.startswith('redis'):
        return True, "RabbitMQ Not configured, but not needed"
    else:
        return False, "RabbitMQ Not configured"


@change_log_level('kafka.client', logging.WARNING)
def check_kafka():
    try:
        client = get_kafka_client()
        consumer = get_kafka_consumer()
    except Exception as e:
        return ServiceStatus(False, "Could not connect to Kafka: %s" % e)

    with client:
        if len(client.cluster.brokers()) == 0:
            return ServiceStatus(False, "No Kafka brokers found")

    with consumer:
        if len(consumer.topics()) == 0:
            return ServiceStatus(False, "No Kafka topics found")

    return ServiceStatus(True, "Kafka seems to be in order")


@change_log_level('urllib3.connectionpool', logging.WARNING)
def check_elasticsearch():
    cluster_health = check_es_cluster_health()
    if cluster_health == 'red':
        return ServiceStatus(False, "Cluster health at %s" % cluster_health)

    doc_id = f'elasticsearch-service-check-{uuid.uuid4().hex[:7]}'
    doc = {'_id': doc_id, 'date': datetime.datetime.now().isoformat()}
    try:
        group_adapter.index(doc, refresh=True)
        assert group_adapter.exists(doc_id), f"Indexed doc not found: {doc_id}"
        group_adapter.delete(doc_id)
    except Exception as exc:
        return ServiceStatus(False, "Something went wrong sending a doc to ES", exc)
    return ServiceStatus(True, "Successfully sent a doc to ES and read it back")


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
    with db.get(meta=meta) as fh:
        res = fh.read()
    db.delete(key=meta.key)
    if res == contents:
        return ServiceStatus(True, "Successfully saved a file to the blobdb")
    return ServiceStatus(False, "Failed to save a file to the blobdb")


def check_celery():
    bad_queues = []

    for queue, threshold in settings.CELERY_HEARTBEAT_THRESHOLDS.items():
        if threshold:
            threshold = datetime.timedelta(seconds=threshold)
            heartbeat = Heartbeat(queue)
            try:
                blockage_duration = heartbeat.get_and_report_blockage_duration()
                heartbeat_time_to_start = heartbeat.get_and_report_time_to_start()
            except HeartbeatNeverRecorded:
                bad_queues.append(f"{queue} has been blocked as long as we can see (max allowed is {threshold})")
            else:
                # We get a lot of self-resolving celery "downtime" under 5 minutes
                # so to make actionable, we never alert on blockage under 5 minutes
                # It is still counted as out of SLA for the celery uptime metric in datadog
                if blockage_duration > max(threshold, datetime.timedelta(minutes=5)):
                    bad_queues.append(
                        f"{queue} has been blocked for {blockage_duration} (max allowed is {threshold})"
                    )
                elif (heartbeat_time_to_start is not None and
                      heartbeat_time_to_start > max(threshold, datetime.timedelta(minutes=5))):
                    bad_queues.append(
                        f"{queue} is delayed for {heartbeat_time_to_start} (max allowed is {threshold})"
                    )

    if bad_queues:
        return ServiceStatus(False, '\n'.join(bad_queues))
    else:
        return ServiceStatus(True, "OK")


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


@ignore_warning(urllib3.exceptions.InsecureRequestWarning)
def check_formplayer():
    url = f'{get_formplayer_url()}/serverup'
    try:
        # Setting verify=False in this request keeps this from failing for urls with self-signed certificates.
        # Allowing this because the certificate will always be self-signed in the "provable deploy"
        # bootstrapping test in commcare-cloud.
        res = requests.get(url, timeout=5, verify=False)
    except requests.exceptions.ConnectTimeout:
        return ServiceStatus(False, f"Could not establish a connection in time {url}")
    except requests.ConnectionError:
        return ServiceStatus(False, f"Could not connect to formplayer: {url}")
    else:
        msg = f"Formplayer returned a {res.status_code} status code: {url}"
        return ServiceStatus(res.ok, msg)


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
}

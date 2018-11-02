"""
A collection of functions which test the most basic operations of various services.
"""
from __future__ import absolute_import
from __future__ import unicode_literals
from io import BytesIO
import attr
import datetime
import logging

from django.core import cache
from django.conf import settings
from django.contrib.auth.models import User
from django.db import connections
from django.db.utils import OperationalError
from celery import Celery
import requests

from corehq.util.timer import TimingContext
from soil import heartbeat

from corehq.apps.hqadmin.escheck import check_es_cluster_health
from corehq.apps.formplayer_api.utils import get_formplayer_url
from corehq.apps.app_manager.models import Application
from corehq.apps.change_feed.connection import get_kafka_client
from corehq.apps.es import GroupES
from corehq.blobs import CODES, get_blob_db
from corehq.elastic import send_to_elasticsearch, refresh_elasticsearch_index
from corehq.util.decorators import change_log_level
from corehq.apps.hqadmin.utils import parse_celery_workers, parse_celery_pings


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


def check_rabbitmq():
    if settings.BROKER_URL.startswith('amqp'):
        amqp_parts = settings.BROKER_URL.replace('amqp://', '').split('/')
        mq_management_url = amqp_parts[0].replace('5672', '15672')
        vhost = amqp_parts[1]
        try:
            vhost_dict = requests.get('http://%s/api/vhosts' % mq_management_url, timeout=2).json()
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
    if cluster_health != 'green':
        return ServiceStatus(False, "Cluster health at %s" % cluster_health)

    doc = {'_id': 'elasticsearch-service-check',
           'date': datetime.datetime.now().isoformat()}
    send_to_elasticsearch('groups', doc)
    refresh_elasticsearch_index('groups')
    hits = GroupES().remove_default_filters().doc_id(doc['_id']).run().hits
    send_to_elasticsearch('groups', doc, delete=True)  # clean up
    if doc in hits:
        return ServiceStatus(True, "Successfully sent a doc to ES and read it back")
    return ServiceStatus(False, "Something went wrong sending a doc to ES")


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
        all_workers = requests.get(
            celery_monitoring + '/api/workers',
            params={'status': True},
            timeout=3,
        ).json()
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


def run_checks(checks_to_do):
    statuses = []
    with TimingContext() as timer:
        for check_name in checks_to_do:
            if check_name not in CHECKS:
                raise UnknownCheckException(check_name)

            check_info = CHECKS[check_name]
            with timer(check_name):
                try:
                    status = check_info['check_func']()
                except Exception as e:
                    status = ServiceStatus(False, "{} raised an error".format(check_name), e)
                status.duration = timer.peek().duration
            statuses.append((check_name, status))
    return statuses


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
        "always_check": True,
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
        "check_func": check_rabbitmq,
    },
}

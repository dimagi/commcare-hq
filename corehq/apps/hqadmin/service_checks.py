"""
A collection of functions which test the most basic operations of various services.
"""
from collections import namedtuple
import json
from StringIO import StringIO

from django.core import cache
from django.conf import settings
from django.contrib.auth.models import User
from restkit import Resource
from soil import heartbeat

from corehq.apps.app_manager.models import Application
from corehq.apps.change_feed.connection import get_kafka_client_or_none
from corehq.blobs import get_blob_db

ServiceStatus = namedtuple("ServiceStatus", "success msg")


def check_redis():
    if 'redis' in settings.CACHES:
        import redis
        rc = cache.caches['redis']
        redis_api = redis.StrictRedis.from_url('%s' % rc._server)
        memory = redis_api.info()['used_memory_human']
        result = rc.set('serverup_check_key', 'test')
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


def check_kafka():
    # TODO mute kafka info
    client = get_kafka_client_or_none()
    if not client:
        return ServiceStatus(False, "Could not connect to Kafka")
    return ServiceStatus(True, "Kafka's fine. Probably.")


def check_touchforms():
    return ServiceStatus(False, "Not implemented")


def check_elasticsearch():
    return ServiceStatus(False, "Not implemented")


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
        for hostname, status in all_workers.items():
            if not status:
                bad_workers.append('* {} celery worker down'.format(hostname))
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
)

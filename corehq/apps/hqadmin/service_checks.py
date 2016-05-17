"""
A collection of functions which test the most basic operations of various services.
"""
from collections import namedtuple
import json
import time
from StringIO import StringIO

from django.core import cache
from django.conf import settings
from restkit import Resource
from soil import heartbeat

from corehq.blobs import get_blob_db

ServiceStatus = namedtuple("ServiceStatus", "success msg")


def check_redis():
    if 'redis' in settings.CACHES:
        rc = cache.caches['redis']
        try:
            import redis
            redis_api = redis.StrictRedis.from_url('%s' % rc._server)
            info_dict = redis_api.info()
            return ServiceStatus(True, "Used Memory: %s" % info_dict['used_memory_human'])
        except Exception, ex:
            return ServiceStatus(False, "Redis connection error: %s" % ex)
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


def check_celery():
    pass


def check_heartbeat():
    is_alive = heartbeat.is_alive()
    return ServiceStatus(is_alive, "OK" if is_alive else "DOWN")


def check_pillowtop():
    return ServiceStatus(False, "Not implemented")


def check_kafka():
    return ServiceStatus(False, "Not implemented")


def check_redis():
    return ServiceStatus(False, "Not implemented")


def check_postgres():
    return ServiceStatus(False, "Not implemented")


def check_couch():
    return ServiceStatus(False, "Not implemented")


def check_celery():
    return ServiceStatus(False, "Not implemented")


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


checks = (
    check_pillowtop,
    check_kafka,
    check_redis,
    check_postgres,
    check_couch,
    check_celery,
    check_touchforms,
    check_elasticsearch,
    check_shared_dir,
    check_blobdb,
)

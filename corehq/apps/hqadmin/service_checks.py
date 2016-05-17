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
from .tasks import dummy_task

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
    res = dummy_task.delay()
    for _ in range(5):
        time.sleep(1)
        if res.ready():
            assert res.result == "expected return value"
            msg = "Celery completed task with status '{}'".format(res.status)
            return ServiceStatus(res.successful(), msg)
    return ServiceStatus(False, "Celery didn't complete task in allotted time")


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


def celery_check():
    try:
        from celery import Celery
        from django.conf import settings
        app = Celery()
        app.config_from_object(settings)
        i = app.control.inspect()
        ping = i.ping()
        if not ping:
            chk = (False, 'No running Celery workers were found.')
        else:
            chk = (True, None)
    except IOError as e:
        chk = (False, "Error connecting to the backend: " + str(e))
    except ImportError as e:
        chk = (False, str(e))

    return chk


def hb_check():
    celery_monitoring = getattr(settings, 'CELERY_FLOWER_URL', None)
    if celery_monitoring:
        try:
            cresource = Resource(celery_monitoring, timeout=3)
            t = cresource.get("api/workers", params_dict={'status': True}).body_string()
            all_workers = json.loads(t)
            bad_workers = []
            for hostname, status in all_workers.items():
                if not status:
                    bad_workers.append('* {} celery worker down'.format(hostname))
            if bad_workers:
                return (False, '\n'.join(bad_workers))
            else:
                hb = heartbeat.is_alive()
        except Exception:
            hb = False
    else:
        try:
            hb = heartbeat.is_alive()
        except Exception:
            hb = False
    return (hb, None)


def redis_check():
    try:
        redis = cache.caches['redis']
        result = redis.set('serverup_check_key', 'test')
    except (InvalidCacheBackendError, ValueError):
        result = True  # redis not in use, ignore
    except:
        result = False
    return (result, None)


def pg_check():
    """check django db"""
    try:
        a_user = User.objects.all()[:1].get()
    except:
        a_user = None
    return (a_user is not None, None)


def couch_check():
    """Confirm CouchDB is up and running, by hitting an arbitrary view."""
    try:
        results = Application.view('app_manager/builds_by_date', limit=1).all()
    except Exception:
        return False, None
    else:
        return isinstance(results, list), None


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

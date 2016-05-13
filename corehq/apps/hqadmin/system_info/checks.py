from collections import namedtuple
from django.core import cache
from django.conf import settings
from django.utils.safestring import mark_safe
from restkit import Resource
import json
from corehq.apps.hqadmin.system_info.utils import human_bytes
from soil import heartbeat

ServiceStatus = namedtuple("ServiceStatus", "success msg")


def check_redis():
    #redis status
    redis_status = ""
    redis_results = ""
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
        amqp_parts = settings.BROKER_URL.replace('amqp://','').split('/')
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

    def get_stats(celery_monitoring, status_only=False, refresh=False):
        cresource = Resource(celery_monitoring, timeout=3)
        endpoint = "api/workers"
        params = {'refresh': 'true'} if refresh else {}
        if status_only:
            params['status'] = 'true'
        try:
            t = cresource.get(endpoint, params_dict=params).body_string()
            return json.loads(t)
        except Exception:
            return {}

    def get_task_html(detailed_stats, worker_name):
        tasks_ok = 'label-success'
        tasks_full = 'label-warning'

        tasks_html = mark_safe('<span class="label %s">unknown</span>' % tasks_full)
        try:
            worker_stats = detailed_stats[worker_name]
            pool_stats = worker_stats['stats']['pool']
            running_tasks = pool_stats['writes']['inqueues']['active']
            concurrency = pool_stats['max-concurrency']
            completed_tasks = pool_stats['writes']['total']

            tasks_class = tasks_full if running_tasks == concurrency else tasks_ok
            tasks_html = mark_safe(
                '<span class="label %s">%d / %d</span> :: %d' % (
                    tasks_class, running_tasks, concurrency, completed_tasks
                )
            )
        except KeyError:
            pass

        return tasks_html

    ret = {}
    celery_monitoring = getattr(settings, 'CELERY_FLOWER_URL', None)
    worker_status = ""
    if celery_monitoring:
        worker_ok = '<span class="label label-success">OK</span>'
        worker_bad = '<span class="label label-important">Down</span>'

        worker_info = []
        worker_status = get_stats(celery_monitoring, status_only=True)
        detailed_stats = get_stats(celery_monitoring, refresh=True)
        for worker_name, status in worker_status.items():
            status_html = mark_safe(worker_ok if status else worker_bad)
            tasks_html = get_task_html(detailed_stats, worker_name)
            worker_info.append(' '.join([worker_name, status_html, tasks_html]))
        worker_status = '<br>'.join(worker_info)
    ret['worker_status'] = mark_safe(worker_status)
    return ServiceStatus(False, "")


def check_heartbeat():
    is_alive = heartbeat.is_alive()
    return ServiceStatus(is_alive, "OK" if is_alive else "DOWN")

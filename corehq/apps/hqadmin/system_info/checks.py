from django.core import cache
from django.conf import settings
from django.utils.safestring import mark_safe
from restkit import Resource
import json
from corehq.apps.hqadmin.system_info.utils import human_bytes
from soil import heartbeat


def check_redis():
    #redis status
    ret = {}
    redis_status = ""
    redis_results = ""
    if 'redis' in settings.CACHES:
        rc = cache.caches['redis']
        try:
            import redis
            redis_api = redis.StrictRedis.from_url('%s' % rc._server)
            info_dict = redis_api.info()
            redis_status = "Online"
            redis_results = "Used Memory: %s" % info_dict['used_memory_human']
        except Exception, ex:
            redis_status = "Offline"
            redis_results = "Redis connection error: %s" % ex
    else:
        redis_status = "Not Configured"
        redis_results = "Redis is not configured on this system!"

    ret['redis_status'] = redis_status
    ret['redis_results'] = redis_results
    return ret


def check_rabbitmq():
    ret ={}
    mq_status = "Unknown"
    if settings.BROKER_URL.startswith('amqp'):
        amqp_parts = settings.BROKER_URL.replace('amqp://','').split('/')
        mq_management_url = amqp_parts[0].replace('5672', '15672')
        vhost = amqp_parts[1]
        try:
            mq = Resource('http://%s' % mq_management_url, timeout=2)
            vhost_dict = json.loads(mq.get('api/vhosts', timeout=2).body_string())
            mq_status = "Offline"
            for d in vhost_dict:
                if d['name'] == vhost:
                    mq_status='RabbitMQ OK'
        except Exception, ex:
            mq_status = "RabbitMQ Error: %s" % ex
    else:
        mq_status = "RabbitMQ Not configured"
    ret['rabbitmq_status'] = mq_status
    return ret


def check_celery_health():

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
    ret['heartbeat'] = heartbeat.is_alive()
    return ret

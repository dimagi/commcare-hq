from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from django.core.management.base import LabelCommand

CELERY_DEPLOY_IN_PROGRESS_FLAG = 'celery_deploy_in_progress'


class Command(LabelCommand):
    help = """
    Sets a celery_deploy_in_progress flag when we purposefully shut down celery during deploy
    """

    def handle(self, *args, **options):
        cache = get_redis_default_cache()
        cache.set(CELERY_DEPLOY_IN_PROGRESS_FLAG, True, timeout=5 * 60)

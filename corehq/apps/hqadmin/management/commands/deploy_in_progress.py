from __future__ import absolute_import
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from django.core.management.base import BaseCommand

DEPLOY_IN_PROGRESS_FLAG = 'deploy_in_progress'


class Command(BaseCommand):
    help = """
    Sets a deploy_in_progress flag when we purposefully shut down services during deploy
    """

    def handle(self, **options):
        cache = get_redis_default_cache()
        cache.set(DEPLOY_IN_PROGRESS_FLAG, True, timeout=5 * 60)

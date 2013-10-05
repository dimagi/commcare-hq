from django.core.management.base import LabelCommand
from django.core import cache


class Command(LabelCommand):
    help = "flush all caches"
    args = ""
    label = ""

    def handle(self, *args, **options):
        rc = cache.get_cache('redis')
        rc.clear()

        mc = cache.get_cache('default')
        mc.clear()

        print "redis and memcached are flushed"






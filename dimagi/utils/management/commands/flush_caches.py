from django.core.management.base import LabelCommand
from django.core import cache
from django.conf import settings


class Command(LabelCommand):
    help = "flush all caches"
    args = ""
    label = ""

    def handle(self, *args, **options):
        print "Clearing caches..."
        for k in settings.CACHES.keys():
            cache_backend = cache.caches[k]
            cache_backend.clear()
            print "\tclearing %s..." % k
        print "all caches are cleared"


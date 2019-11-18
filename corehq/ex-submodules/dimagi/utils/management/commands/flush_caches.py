from django.core.management.base import BaseCommand
from django.core import cache
from django.conf import settings


class Command(BaseCommand):
    help = "flush all caches"

    def handle(self, **options):
        print("Clearing caches...")
        for k in settings.CACHES:
            cache_backend = cache.caches[k]
            cache_backend.clear()
            print("\tclearing %s..." % k)
        print("all caches are cleared")


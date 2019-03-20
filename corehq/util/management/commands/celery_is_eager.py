from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Prints "true" if settings.CELERY_TASK_ALWAYS_EAGER is truthy, else "false".'

    def handle(self, **options):
        always_eager = getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)
        print('true' if always_eager else 'false')

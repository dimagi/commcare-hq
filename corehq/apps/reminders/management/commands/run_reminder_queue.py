from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    # This command is referenced by a supervisor process in commcare-cloud.
    # Once that's removed, this can be removed.

    def handle(self, **options):
        return

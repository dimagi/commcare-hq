from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand
from corehq.warehouse.const import STAGING_TABLES
from corehq.warehouse.models import get_cls_by_slug


USAGE = """Usage: ./manage.py clear_staging_records

Removes all records from staging tables. Should only be used during development.
"""


class Command(BaseCommand):
    """
    Example: ./manage.py clear_staging_records
    """
    help = USAGE

    def handle(self, **options):
        for slug in STAGING_TABLES:
            model = get_cls_by_slug(slug)
            model.clear_records()

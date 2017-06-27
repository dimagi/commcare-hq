from django.core.management import BaseCommand
from corehq.warehouse.const import STAGING_TABLES
from corehq.warehouse.models import get_cls_by_slug


USAGE = """Usage: ./manage.py clear_staging_records
"""


class Command(BaseCommand):
    """
    Example: ./manage.py stage_table group_staging 222617b9-8cf0-40a2-8462-7f872e1f1344
    """
    help = USAGE

    def handle(self, **options):
        for slug in STAGING_TABLES:
            model = get_cls_by_slug(slug)
            model.clear_records()

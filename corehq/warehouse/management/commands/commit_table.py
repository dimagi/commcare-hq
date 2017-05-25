from django.core.management import BaseCommand, CommandError
from corehq.warehouse.models import get_cls_by_slug

from corehq.warehouse.const import (
    DIM_TABLES,
    FACT_TABLES,
)


USAGE = """Usage: ./manage.py commit_table <slug>

Slugs:
{}
""".format('\n'.join(DIM_TABLES + FACT_TABLES))


class Command(BaseCommand):
    """
    Example: ./manage.py commit_table group_dim

    Takes the current data in the staging table and commits it to the production table.
    """
    help = USAGE
    args = '<slug>'

    def add_arguments(self, parser):
        parser.add_argument('slug')

    def handle(self, slug, **options):
        model = get_cls_by_slug(slug)

        if not model or (slug not in DIM_TABLES and slug not in FACT_TABLES):
            raise CommandError('{} is not a valid slug. \n\n {}'.format(slug, USAGE))

        model.load()

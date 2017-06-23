from django.core.management import BaseCommand, CommandError
from dimagi.utils.parsing import string_to_utc_datetime
from corehq.warehouse.const import ALL_TABLES
from corehq.warehouse.models import get_cls_by_slug


USAGE = """Usage: ./manage.py commit_table <slug> -s <start_datetime> -e <end_datetime>

Slugs:

{}

""".format('\n'.join(sorted(ALL_TABLES)))


class Command(BaseCommand):
    """
    Example: ./manage.py stage_table group_staging -s 2017-05-01 -e 2017-06-01
    """
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('slug')

        parser.add_argument(
            '-s',
            '--start_datetime',
            dest='start',
            required=True,
            help='Specifies the last modified datetime at which records should start being included',
            type=_valid_date
        )
        parser.add_argument(
            '-e',
            '--end_datetime',
            dest='end',
            required=True,
            help='Specifies the last modified datetime at which records should stop being included',
            type=_valid_date
        )

    def handle(self, slug, **options):
        start = options.get('start')
        end = options.get('end')

        try:
            model = get_cls_by_slug(slug)
        except KeyError:
            raise CommandError('{} is not a valid slug. \n\n {}'.format(slug, USAGE))
        model.commit(start, end)


def _valid_date(date_str):
    try:
        return string_to_utc_datetime(date_str)
    except ValueError:
        raise CommandError('Not a valid date string: {}'.format(date_str))

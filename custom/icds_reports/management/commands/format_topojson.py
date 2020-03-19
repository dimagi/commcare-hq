from django.core.management import BaseCommand

from custom.icds_reports.utils.topojson_util.topojson_util import get_topojson_file_for_level


class Command(BaseCommand):
    help = "Format a topojson file so it can be used in other programs (e.g. mapshaper)"

    def add_arguments(self, parser):
        parser.add_argument('level')
        parser.add_argument('output_file')

    def handle(self, level, output_file, *args, **kwargs):
        topojson_file = get_topojson_file_for_level(level)
        with open(output_file, 'w+') as f:
            f.write(topojson_file.get_formatted_topojson())

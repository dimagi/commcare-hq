import json

from django.core.management import BaseCommand

from custom.icds_reports.utils.topojson_util.topojson_util import (
    get_topojson_file_for_level,
    copy_custom_metadata,
)


class Command(BaseCommand):
    help = "Merge a new topojson file with our existing files to add the shared attributes."

    def add_arguments(self, parser):
        parser.add_argument('level')
        parser.add_argument('new_file')

    def handle(self, level, new_file, *args, **kwargs):
        existing_topojson_file = get_topojson_file_for_level(level)
        with open(new_file) as f:
            new_topojson = json.loads(f.read())

        copy_custom_metadata(existing_topojson_file.topojson, new_topojson)
        with open(new_file, 'w+') as f:
            f.write(json.dumps(new_topojson))

from django.core.management import BaseCommand, CommandError

from custom.icds_reports.utils.topojson_util.topojson_util import (
    get_block_topojson_file,
    get_district_topojson_file,
    get_state_topojson_file,
)


class Command(BaseCommand):
    help = "Create Split TopoJSON files for districts and blocks"

    def add_arguments(self, parser):
        parser.add_argument('level')
        parser.add_argument('output_file')

    def handle(self, level, output_file, *args, **kwargs):
        level_function_map = {
            "state": get_state_topojson_file,
            "district": get_district_topojson_file,
            "block": get_block_topojson_file,
        }
        if level not in level_function_map:
            raise CommandError("Level must be one of: {}".format(', '.join(level_function_map.keys())))

        topojson_file = level_function_map[level]()
        with open(output_file, 'w+') as f:
            f.write(topojson_file.get_formatted_topojson())

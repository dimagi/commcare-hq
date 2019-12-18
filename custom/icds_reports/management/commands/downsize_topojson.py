import json
import os
import subprocess
from django.core.management import BaseCommand

from custom.icds_reports.utils.topojson_util.topojson_util import get_topojson_file_for_level, \
    get_topojson_directory, copy_custom_metadata


class Command(BaseCommand):
    help = "Downsize a topojson file by a given percentage."

    def add_arguments(self, parser):
        parser.add_argument('level')
        parser.add_argument('output_file')
        parser.add_argument('percent', type=int)

    def handle(self, level, output_file, percent, *args, **kwargs):
        topojson_file = get_topojson_file_for_level(level)
        output_dir = get_topojson_directory()
        output_file_path = os.path.join(output_dir, output_file)
        tmp_input_filename = os.path.join(output_dir, 'topojson_tmp_in.topojson')
        with open(tmp_input_filename, 'w+') as f:
            f.write(topojson_file.get_formatted_topojson())

        tmp_output_filename = os.path.join(output_dir, 'topojson_tmp_out.topojson')
        mapshaper_command = f"mapshaper {tmp_input_filename} -simplify {percent}% -o {tmp_output_filename}"
        print(f'calling: {mapshaper_command}')
        subprocess.call(mapshaper_command, shell=True)

        # now add metadata back
        with open(tmp_output_filename) as f:
            output_topojson = json.loads(f.read())

        copy_custom_metadata(topojson_file.topojson, output_topojson)
        with open(output_file_path, 'w+') as f:
            f.write(json.dumps(output_topojson))

        print(f'Topojson output to {output_file_path}')

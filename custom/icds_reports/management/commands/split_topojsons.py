import json
import subprocess

from pathlib import Path

import os
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = "Create Split TopoJSON files for districts and blocks"

    def handle(self, *args, **kwargs):
        input_dir = os.path.join(Path(__file__).parent.parent.parent, 'static', 'js', 'topojsons')
        output_dir = os.path.join(Path(__file__).parent.parent.parent, 'utils', 'topojson_util', 'static')
        # loading block topojson object
        block_topojson_filename = os.path.join(input_dir, 'blocks_v3.topojson.js')
        block_topojson_file = open(block_topojson_filename)
        block_topojson_file_content = block_topojson_file.read()
        # strip off 'var BLOCK_TOPOJSON = ' from the front of the file and '\n;' from the end
        block_topojson_text = block_topojson_file_content[21:][:-2]
        block_topojson = json.loads(block_topojson_file_content[21:][:-2])

        # the mapshaper command needs the variable assignment removed, so save it to a temporary file
        tmp_block_filename = os.path.join(input_dir, 'blocks_tmp.topojson')
        with open(tmp_block_filename, 'w+') as f:
            f.write(block_topojson_text)

        # loading district topojson object
        district_topojson_filename = os.path.join(input_dir, 'districts_v2.topojson.js')
        district_topojson_file = open(district_topojson_filename)
        district_topojson_file_content = district_topojson_file.read()
        # strip off 'var DISTRICT_TOPOJSON = ' from the front of the file
        district_topojson = json.loads(district_topojson_file_content[24:][:-2])

        # create state district map. end result will look like this:
        # {
        #   "state name": {
        #     "districts": [
        #       "district name",
        #       "district name 2",
        #     ]
        #   }
        # }
        state_district_map = {}
        for district in block_topojson['objects'].keys():
            for state, data in district_topojson['objects'].items():
                for district2 in data['geometries']:
                    if district == district2['id']:
                        if state in state_district_map:
                            state_district_map[state]['districts'].append(district)
                        else:
                            state_district_map[state] = {}
                            state_district_map[state]['districts'] = [district]

        # create actual shape data files for each of the states
        for state, data in state_district_map.items():
            district_list = data['districts']
            districts = ','.join(district_list)
            file_name_part = state.replace(' &', '').replace('&', '').replace(' ', '_').lower()
            output_filename = '{}_blocks_v3.topojson'.format(file_name_part)
            output_file_path = os.path.join(output_dir, 'blocks', output_filename)

            # breaking block topojson for each state using mapshaper : https://www.npmjs.com/package/mapshaper
            mapshaper_command = "mapshaper {} -o target='{}' {}".format(
                tmp_block_filename, districts, output_file_path
            )
            subprocess.call(mapshaper_command, shell=True)

            # create new topojson file using the topojson created above
            with open(output_file_path) as state_topojson:
                state_topojson_file_content = state_topojson.read()

            # copy center, height and scale data into new topojson from orginal block topojson
            state_topojson_js_json = json.loads(state_topojson_file_content)
            for district in state_topojson_js_json['objects'].keys():
                district_data = state_topojson_js_json['objects'][district]
                district_data['center'] = block_topojson['objects'][district]['center']
                district_data['height'] = block_topojson['objects'][district]['height']
                district_data['scale'] = block_topojson['objects'][district]['scale']

            state_topojson_js = json.dumps(state_topojson_js_json)

            with open(output_file_path, 'w+') as state_topojson_js_file:
                state_topojson_js_file.write(state_topojson_js)

            data['file_name'] = output_filename

        # saving the state district data with file name of topojson for each state
        state_district_map_file = open(os.path.join(output_dir, 'district_topojson_data.json'), 'w+')
        state_district_map_file.write(json.dumps(state_district_map, indent=2))
        state_district_map_file.close()

        block_topojson_file.close()
        district_topojson_file.close()
        os.remove(tmp_block_filename)
        print('done')

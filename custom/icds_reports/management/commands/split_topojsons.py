import json
import subprocess

from pathlib import Path

import os
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = "Create Split TopoJSON files for districts and blocks"

    def handle(self, *args, **kwargs):
        input_dir = os.path.join(Path(__file__).parent.parent.parent, 'static', 'js', 'topojsons')
        # loading block topojson object
        block_topojson_file = open(os.path.join(input_dir, 'blocks_v3.topojson.js'))
        block_topojson_file_content = block_topojson_file.read()
        block_topojson = json.loads(block_topojson_file_content[21:])


        # loading district topojson object
        district_topojson_file = open(os.path.join('districts_v2.topojson.js'))
        district_topojson_file_content = district_topojson_file.read()
        district_topojson = json.loads(district_topojson_file_content[24:])

        # creating state district map for mapping
        state_district_map = {}
        for district in block_topojson['objects'].keys():
            for state, data in district_topojson['objects'].items():
                for district2 in data['geometries']:
                    if district == district2['id']:
                        if state in state_district_map:
                            state_district_map[state]['districts'].append(district)
                            state_district_map[state]['districts'].append(district)
                        else:
                            state_district_map[state] = {}
                            state_district_map[state]['districts'] = [district]


        # creating files for each of the state
        for state, data in state_district_map.items():
            district_list = data['districts']
            districts = ','.join(district_list)
            file_name_part = state.replace(' &', '').replace('&', '').replace(' ', '_').lower()
            file_path = '"topojson/' + file_name_part + '_blocks_v3.topojson"'

            # breaking block topojson for each state using mapshaper : https://www.npmjs.com/package/mapshaper
            subprocess.call("mapshaper block_topojson.topojson -o target='" + districts + "' " + file_path, shell=True)

            # create new topojson file using the topojson created above
            state_file_name = 'topojson/' + file_name_part + '_blocks_v3.topojson'
            state_topojson = open(state_file_name)
            state_topojson_file_content = state_topojson.read()

            # copy center, height and scale data into new topojson from orginal block topojson
            state_topojson_js_json = json.loads(state_topojson_file_content)
            for district in state_topojson_js_json['objects'].keys():
                district_data = state_topojson_js_json['objects'][district]
                district_data['center'] = block_topojson['objects'][district]['center']
                district_data['height'] = block_topojson['objects'][district]['height']
                district_data['scale'] = block_topojson['objects'][district]['scale']


            state_topojson_js = json.dumps(state_topojson_js_json)

            state_topojson_js_file = open('topojson/js/' + file_name_part + '_blocks_v3.topojson', 'w+')
            state_topojson_js_file.write(state_topojson_js)
            state_topojson_js_file.close()

            data['file_name'] = state_file_name


        # saving the state district data with file name of topojson for each state
        state_district_map_file = open('district_topojson_data.json', 'w+')
        state_district_map_file.write(json.dumps(state_district_map))
        state_district_map_file.close()


        block_topojson_file.close()
        district_topojson_file.close()
        print('done')

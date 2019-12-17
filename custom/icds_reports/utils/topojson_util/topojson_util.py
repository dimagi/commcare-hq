import json
import os
from collections import namedtuple
from pathlib import Path


TopojsonFile = namedtuple('TopojsonFile', ['path', 'topojson_text', 'topojson'])


def get_topojson_directory():
    return os.path.join(Path(__file__).parent.parent.parent, 'static', 'js', 'topojsons')


def get_block_topojson_file():
    path = os.path.join(get_topojson_directory(), 'blocks_v3.topojson.js')
    with open(path) as f:
        content = f.read()
        # strip off 'var BLOCK_TOPOJSON = ' from the front of the file and '\n;' from the end
        topojson_text = content[21:][:-2]
        return TopojsonFile(path, topojson_text, json.loads(topojson_text))


def get_topojson_for_district(district):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

    district_topojson_data_path = os.path.join(path, 'district_topojson_data.json')
    district_topojson_data = json.loads(open(district_topojson_data_path, encoding='utf-8').read())

    for state, data in district_topojson_data.items():
        if district in data['districts']:
            with open(os.path.join(path, 'blocks/' + data['file_name']), encoding='utf-8') as f:
                return json.loads(f.read())

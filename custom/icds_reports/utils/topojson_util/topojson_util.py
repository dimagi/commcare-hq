import json
import os
from pathlib import Path


def get_topojson_directory():
    return os.path.join(Path(__file__).parent.parent.parent, 'static', 'js', 'topojsons')


def get_topojson_for_district(district):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

    district_topojson_data_path = os.path.join(path, 'district_topojson_data.json')
    district_topojson_data = json.loads(open(district_topojson_data_path, encoding='utf-8').read())

    for state, data in district_topojson_data.items():
        if district in data['districts']:
            with open(os.path.join(path, 'blocks/' + data['file_name']), encoding='utf-8') as f:
                return json.loads(f.read())

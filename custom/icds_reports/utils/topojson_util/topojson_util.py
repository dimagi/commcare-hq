import json
import os

def getTopoJsonForDistrict(district):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

    district_topojson_data_path = os.path.join(path, 'district_topojson_data.json')
    district_topojson_data = json.loads(open(district_topojson_data_path, encoding='utf-8').read())

    for state, data in district_topojson_data.items():
        if district in data['districts']:
            with open(os.path.join(path, 'blocks/' + data['file_name']), encoding='utf-8') as f:
                return json.loads(f.read())

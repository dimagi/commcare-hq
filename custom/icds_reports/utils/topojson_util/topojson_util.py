import json
import logging
import os
from pathlib import Path

import attr

from corehq.util.soft_assert import soft_assert


@attr.s
class TopojsonFile:
    path = attr.ib()
    topojson_text = attr.ib()
    topojson = attr.ib()

    def get_formatted_topojson(self):
        return json.dumps(self.topojson, indent=2)


def get_topojson_directory():
    return os.path.join(Path(__file__).parent.parent.parent, 'static', 'js', 'topojsons')


def _get_topojson_file(filename, truncate_before):
    path = os.path.join(get_topojson_directory(), filename)
    with open(path) as f:
        content = f.read()
        if not truncate_before:
            # no truncation necessary if it's already a json file
            topojson_text = content
        else:
            # strip off e.g. 'var BLOCK_TOPOJSON = ' from the front of the file and '\n;' from the end
            topojson_text = content[truncate_before:][:-2]

        return TopojsonFile(path, topojson_text, json.loads(topojson_text))


def get_block_topojson_file():
    return _get_topojson_file('blocks_v3.topojson.js', truncate_before=21)


def get_district_topojson_file():
    return _get_topojson_file('districts_v2.topojson.js', truncate_before=24)


def get_district_v3_topojson_file():
    return _get_topojson_file('districts_v3_small.topojson', truncate_before=0)


def get_state_topojson_file():
    return _get_topojson_file('states_v2.topojson.js', truncate_before=21)


def get_state_v3_topojson_file():
    return _get_topojson_file('states_v3_small.topojson', truncate_before=0)


def get_topojson_file_for_level(level):
    level_function_map = {
        "state": get_state_topojson_file,
        "district": get_district_topojson_file,
        "block": get_block_topojson_file,
    }
    if level not in level_function_map:
        raise ValueError("Level must be one of: {}".format(', '.join(level_function_map.keys())))

    return level_function_map[level]()


def copy_custom_metadata(from_topojson, to_topojson):
    for location_name, location_data in to_topojson['objects'].items():
        if location_name in from_topojson['objects']:
            location_data['center'] = from_topojson['objects'][location_name]['center']
            location_data['height'] = from_topojson['objects'][location_name]['height']
            location_data['scale'] = from_topojson['objects'][location_name]['scale']
        else:
            raise ValueError(f'{location_name} was not found in source topojson!')


def get_block_topojson_for_state(state):
    path = get_topojson_directory()
    district_topojson_data = get_district_topojson_data()
    if state in district_topojson_data:
        filename = district_topojson_data[state]['file_name']
        if filename:
            with open(os.path.join(path, 'blocks/' + filename), encoding='utf-8') as f:
                return json.loads(f.read())
    else:
        logging.error('State {} not found in district topojson file'.format(state))


def get_district_topojson_data():
    district_topojson_data_path = os.path.join(get_topojson_directory(), 'district_topojson_data.json')
    with open(district_topojson_data_path, encoding='utf-8') as f:
        return json.loads(f.read())


def get_map_name(location):
    """
    Gets the "map name" of a SQLLocation, defaulting to the location's name if not available.
    """
    if not location:
        return

    if 'map_location_name' in location.metadata and location.metadata['map_location_name']:
        return location.metadata['map_location_name']
    else:
        return location.name

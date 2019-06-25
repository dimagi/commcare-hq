from __future__ import absolute_import, unicode_literals

import json
import os

from lxml import etree

from corehq.apps.couch_sql_migration.couchsqlmigration import (
    map_form_ids,
)


def test_map_form_ids():
    for form_id in form_ids:
        yield check_missing_value_error_form, form_id


def check_missing_value_error_form(form_id):
    form_json = json.loads(read_data_file(form_id + '.json'))
    form_xml_root = etree.XML(read_data_file(form_id + '.xml'))
    ignore_paths = []
    map_form_ids(form_json['form'], form_xml_root, id_map, ignore_paths)
    assert True  # assert map_form_ids() does not raise MissingValueError


def read_data_file(filename, binary=False):
    base_path = os.path.dirname(__file__)
    mode = 'rb' if binary else 'r'
    with open(os.path.sep.join((base_path, 'data', filename)), mode) as f:
        return f.read()


form_ids = (
    '5af63d3a38b1444a815985dcbcc7dc1a',
    'f7d4a40b4eaf45b39a21daaa3b1f069f',
    '911fc8fbb610459c9b930fd65f3b5ace',
    '437fbde5d1f54044a37af54ab6a4acaf',
    '6a63fe1512894bb1882f0ebcd2c296d0',
    '7f28b4e409884d0c838678260f9c34dd',
    'ad8985d825ee42daa0d35c8a5c6f07c0',
    'fb76ddf670964731ae40c16e2da8b35e',
    'c17ce074dee54e17822c1a54e200989e',
)
id_map = {
    '8f14226132de499386aca46212970fa2': 'bcff8fb0f1e843469bc37a4d91df7c0f',
    'a71deea898a84f8bb95b6dc723303b8b': 'ef4049861d0d43a4bfc9a9f1a6ca031e',
    '14644d044264483abb8c557accc4b52c': 'fb05a32dd3c743f6b8777af43ce565cd',
    '512b05522b2c449e9add92425c831483': 'f5e4eac4e92f4e4db614cb269f8bd897',
    '3cc8009fda194040bbeae8248d855b40': '1ebc17b280af4bbb8af6c7c66b5119ae',
    'e4144e11519047f1b666d7361dcbb6cc': '103a90f39021496c90e58dc332a90320',
    'afbea200129a4ba9a33636cb2b525c35': '650dac48fe534961a1a17c7248ce76c6',
}

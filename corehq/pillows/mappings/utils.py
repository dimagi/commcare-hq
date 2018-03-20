from __future__ import absolute_import
from __future__ import unicode_literals
import json
import os

from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING


def mapping_from_json(filename):
    with open(os.path.join(os.path.dirname(__file__), filename)) as f:
        data = (f.read()
                .replace('"__DATE_FORMATS_STRING__"', json.dumps(DATE_FORMATS_STRING))
                .replace('"__DATE_FORMATS_ARR__"', json.dumps(DATE_FORMATS_ARR)))
        mapping = json.loads(data)
    return mapping

from __future__ import absolute_import
from __future__ import unicode_literals
import json


class ElasticTestMixin(object):

    def checkQuery(self, query, json_output, is_raw_query=False):
        if is_raw_query:
            raw_query = query
        else:
            raw_query = query.raw_query
        msg = "Expected Query:\n{}\nGenerated Query:\n{}".format(
            json.dumps(json_output, indent=4),
            json.dumps(raw_query, indent=4),
        )
        # NOTE: This method thinks [a, b, c] != [b, c, a]
        self.assertEqual(raw_query, json_output, msg=msg)

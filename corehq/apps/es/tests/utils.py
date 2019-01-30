from __future__ import absolute_import
from __future__ import unicode_literals
import json


class ElasticTestMixin(object):

    def checkQuery(self, query, json_output):
        msg = "Expected Query:\n{}\nGenerated Query:\n{}".format(
            json.dumps(json_output, indent=4),
            json.dumps(query, indent=4),
        )
        # NOTE: This method thinks [a, b, c] != [b, c, a]
        self.assertEqual(query, json_output, msg=msg)

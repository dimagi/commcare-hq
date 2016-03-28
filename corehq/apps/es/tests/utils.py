import json


class ElasticTestMixin(object):
    def checkQuery(self, query, json_output):
        msg = "Expected Query:\n{}\nGenerated Query:\n{}".format(
            json.dumps(json_output, indent=4),
            query.dumps(pretty=True),
        )
        # NOTE: This method thinks [a, b, c] != [b, c, a]
        self.assertEqual(query.raw_query, json_output, msg=msg)

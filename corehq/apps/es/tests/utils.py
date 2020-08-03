import json
from nose.plugins.attrib import attr


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


def es_test(test):
    """Decorator for tagging ElasticSearch tests

    :param test: A test class, method, or function.
    """
    return attr(es_test=True)(test)

import re

from corehq.elastic import SIZE_LIMIT


class FacetResult(object):
    def __init__(self, raw, facet):
        self.facet = facet
        self.raw = raw
        self.result = raw.get(self.facet.name, {}).get(self.facet.type, {})


class Facet(object):
    name = None
    type = None
    params = None
    result_class = FacetResult

    def __init__(self):
        raise NotImplementedError()

    def parse_result(self, result):
        return self.result_class(result, self)


class TermsResult(FacetResult):
    def counts_by_term(self):
        return {d['term']: d['count'] for d in self.result}


class TermsFacet(Facet):
    type = "terms"
    result_class = TermsResult

    def __init__(self, term, name, size=None):
        assert re.match(r'\w+$', name), \
            "Facet names must be valid python variable names, was {}".format(name)
        self.name = name
        self.params = {
            "field": term,
            "size": size if size is not None else SIZE_LIMIT,
            "shard_size": SIZE_LIMIT,
        }


class DateHistogram(Facet):
    type = "date_histogram"

    def __init__(self, name, datefield, interval):
        self.name = name
        self.params = {
            "field": datefield,
            "interval": interval
        }

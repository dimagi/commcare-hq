"""
Faceted Queries
---------------

Elasticsearch can perform some aggregations using "facets".

Here is an example used to calculate how many new pregnancy cases each user has
opened in a certain date range.

.. code-block:: python

    res = (CaseES()
           .domain(self.domain)
           .case_type('pregnancy')
           .date_range('opened_on', gte=startdate, lte=enddate))
           .terms_facet('opened_by', 'user')
           .size(0)

    facet_result = res.facets.user
    creations_by_user  = facet_result.counts_by_term()

There's a bit of magic happening here - you can access the raw json data from
this facet via ``res.facet('user', 'terms')`` if you'd prefer to skip it.

The ``res`` object has a ``facets`` property, which returns a namedtuple
pointing to the wrapped facet results.  The name provided at instantiation is
used here (``user`` in this example).

The wrapped ``facet_result`` object has a ``result`` property containing the
facet data, as well as utilties for parsing that data into something more
useful. For example, the ``TermsFacet`` result also has a ``counts_by_term``
method that returns a ``{term: count}`` dictionary, which is normally what you
want.

As of this writing, there's not much else developed, but it's pretty easy to
add support for other facet types and more results processing
"""
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
    """
    Perform a basic count aggregation.

    This class can be instantiated by the ``ESQuery.terms_facet`` method.

    :param term: the document field to use
    :param name: what do you want to call this facet?
    """
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
    """
    Aggregate by date range.  This can answer questions like "how many forms
    were created each day?".

    This class can be instantiated by the ``ESQuery.date_histogram`` method.

    :param name: what do you want to call this facet?
    :param datefield: the document's date field to look at
    :param interval: the date interval to use: "year", "quarter", "month",
        "week", "day", "hour", "minute", "second"
    """
    type = "date_histogram"

    def __init__(self, name, datefield, interval):
        self.name = name
        self.params = {
            "field": datefield,
            "interval": interval
        }

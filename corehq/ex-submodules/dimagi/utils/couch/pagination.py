from __future__ import absolute_import
from dimagi.utils.couch.database import is_bigcouch
from django.http import HttpResponse
import json
from restkit.errors import RequestFailed
from six.moves import filter

DEFAULT_DISPLAY_LENGTH = "10"
DEFAULT_START = "0"
DEFAULT_ECHO = "0"


class DatatablesParams(object):

    def __init__(self, count, start, desc, echo, search=None):
        self.count = count
        self.start = start
        self.desc = desc
        self.echo = echo
        self.search = search

    def __repr__(self):
        return json.dumps({
            'start': self.start,
            'count': self.count,
            'echo': self.echo,
        }, indent=2)

    @classmethod
    def from_request_dict(cls, query):

        count = int(query.get("iDisplayLength", DEFAULT_DISPLAY_LENGTH))

        start = int(query.get("iDisplayStart", DEFAULT_START))

        # sorting
        desc_str = query.get("sSortDir_0", "desc")
        desc = desc_str == "desc"

        echo = query.get("sEcho", DEFAULT_ECHO)

        search = query.get("sSearch", "")

        return DatatablesParams(count, start, desc, echo, search)


class CouchPaginator(object):
    """
    Allows pagination of couchdbkit ViewResult objects.
    This class is meant to be used in conjunction with datatables.net
    ajax APIs, to allow you to paginate your views efficiently.
    """


    def __init__(self, view_name, generator_func, search=True,
                 search_preprocessor=lambda x: x, use_reduce_to_count=False,
                 view_args=None, database=None):
        """
        The generator function should be able to convert a couch
        view results row into the appropriate json.

        No searching will be done unless you pass in a search view
        """
        self._view = view_name
        self._generator_func = generator_func
        self._search = search
        self._search_preprocessor = search_preprocessor
        self._view_args = view_args or {}
        assert bool(database), "You must provide a database"
        self.database = database
        self.use_reduce_to_count = use_reduce_to_count


    def get_ajax_response(self, request, default_display_length=DEFAULT_DISPLAY_LENGTH,
                          default_start=DEFAULT_START, extras=None):
        """
        From a datatables generated ajax request, return the appropriate
        httpresponse containing the appropriate objects objects.

        Extras allows you to override any individual parameter that gets
        returned
        """
        extras = extras or {}
        query = request.GET
        params = DatatablesParams.from_request_dict(query)

        # search
        search_key = query.get("sSearch", "")
        if self._search and search_key:
            items = self.database.view(self._view, skip=params.start,
                                       limit=params.count, descending=params.desc,
                                       key=self._search_preprocessor(search_key),
                                       reduce=False, **self._view_args)
            if params.start + len(items) < params.count:
                total_display_rows = len(items)
            else:
                total_display_rows = self.database.view(self._view,
                                                        key=self._search_preprocessor(search_key),
                                                        reduce=True).one()["value"]
            total_rows = items.total_rows

        else:
            # only reduce if the _search param is set.
            # TODO: get this more smartly from the couch view
            kwargs = {}
            if self._search:
                kwargs.update(skip=params.start, limit=params.count, descending=params.desc, reduce=False)
                kwargs.update(self._view_args)
            else:
                kwargs.update(skip=params.start, limit=params.count, descending=params.desc)
                kwargs.update(self._view_args)
            items = self.database.view(self._view, **kwargs)

            if self.use_reduce_to_count:
                kwargs.update(reduce=True, group_level=0, include_docs=False, skip=0, limit=None)
                total_display_rows = total_rows = (
                    self.database.view(self._view, **kwargs).one() or {'value': 0}
                )['value']
            else:
                total_rows = items.total_rows
                total_display_rows = items.total_rows

        # this startkey, endkey business is not currently used,
        # but is a better way to search eventually.
        # for now the skip parameter is fast enough to suit our scale
        startkey, endkey = None, None
        all_json = []
        for row in items:
            if not startkey:
                startkey = row["key"]
            endkey = row["key"]
            row = self._generator_func(row)
            if row:
                all_json.append(row)

        to_return = {"sEcho": params.echo,
                     "iTotalDisplayRecords": total_display_rows,
                     "iTotalRecords": total_rows,
                     "aaData": all_json}

        to_return.update(extras)

        return HttpResponse(json.dumps(to_return))


class LucenePaginator(object):
    """
    Allows pagination of couchdbkit ViewResult objects, integrated with
    lucene.  This is a slightly different model than the other one, though
    the functionality could probably be shared better.
    """

    def __init__(self, search_view_name, generator_func, database):
        """
        The generator function should be able to convert a couch
        view results row into the appropriate json.
        """
        self._search_view = search_view_name
        self._generator_func = generator_func
        self.database = database

    def get_search_params(self):
        # the difference is:
        # on couch lucene: /[db]/_fti/_design/[ddoc]/[search view]
        # on cloudant: /[db]/_design/[ddoc]/_search/[search view]
        # this magic combination of args makes it work for each one in couchdbkit
        if is_bigcouch():
            ddoc, view = self._search_view.split("/")
            return {
                'view_name': '%s/_search/%s' % (ddoc, view),
                'handler': "_design",
            }
        else:
            return {
                'view_name': self._search_view,
                'handler': "_fti/_design",
            }

    def get_results(self, search_query, limit, skip):
        results = self.database.search(
            q=search_query,
            limit=limit,
            skip=skip,
            **self.get_search_params()
        )
        rows = (self._generator_func(row) for row in results)
        try:
            return results.total_rows, filter(None, rows)
        except RequestFailed:
            # just ignore poorly formatted search terms for now
            return 0, []


    def get_ajax_response(self, request, search_query, extras=None):
        """
        From a datatables generated ajax request, return the appropriate
        httpresponse containing the appropriate objects objects.

        Extras allows you to override any individual paramater that gets
        returned
        """
        extras = extras or {}
        query = request.POST if request.method == "POST" else request.GET
        params = DatatablesParams.from_request_dict(query)
        total_rows, all_json = self.get_results(search_query, params.count, params.start)

        to_return = {"sEcho": params.echo,
                     "iTotalDisplayRecords": total_rows,
                     "aaData": list(all_json)}

        to_return.update(extras)

        return HttpResponse(json.dumps(to_return))

from base64 import b64encode
from urllib.parse import urlencode

from tastypie.paginator import Paginator

from corehq.apps.api.util import get_datasource_records


class NoCountingPaginator(Paginator):
    """
    The default paginator contains the total_count value, which shows how
    many objects are in the underlying object list. Obtaining this data from
    the database is inefficient, especially with large datasets, and unfiltered API requests.

    This class does not perform any counting and return 'null' as the value of total_count.

    See:
        * http://django-tastypie.readthedocs.org/en/latest/paginator.html
        * http://wiki.postgresql.org/wiki/Slow_Counting
    """

    def get_previous(self, limit, offset):
        if offset - limit < 0:
            return None

        return self._generate_uri(limit, offset - limit)

    def get_next(self, limit, offset, count):
        """
        Always generate the next URL even if there may be no records.
        """
        return self._generate_uri(limit, offset + limit)

    def get_count(self):
        """
        Don't do any counting.
        """
        return None


class DoesNothingPaginator(Paginator):
    def page(self):
        return {
            self.collection_name: self.objects,
            "meta": {'total_count': self.get_count()}
        }


class DoesNothingPaginatorCompat(Paginator):
    """Similar to DoesNothingPaginator this paginator
    does not do any pagination but it preserves the
    pagination fields for backwards compatibility.
    """
    def page(self):
        count = self.get_count()
        meta = {
            'offset': 0,
            'limit': None,
            'total_count': count,
            'previous': None,
            'next': None,
        }

        return {
            self.collection_name: self.objects,
            'meta': meta,
        }


def response_for_cursor_based_pagination(query, request_params, datasource_adapter):
    """Creates a response dictionary that can be used for cursor based pagination
     :returns: The response dictionary
    """
    records = get_datasource_records(query, datasource_adapter)
    return {
        "objects": records,
        "meta": {
            "next": _get_next_url_params(records),
            "limit": request_params["limit"]
        }
    }


def _get_next_url_params(datasource_records):
    """ Constructs the query string containing a base64-encoded cursor that points to the last entry in
    `datasource_records`
    :returns: The query string"""
    if not datasource_records["rows"]:
        return None
    last_object = datasource_records["rows"][-1]
    cursor_params = {"last_doc_id": last_object[0], "last_inserted_at": last_object[1]}
    encoded_cursor = b64encode(urlencode(cursor_params).encode('utf-8'))
    next_params = {'cursor': encoded_cursor}
    return f'?{urlencode(next_params)}'

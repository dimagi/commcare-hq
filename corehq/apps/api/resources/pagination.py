import logging
from base64 import b64encode, b64decode
from urllib.parse import urlencode

from django.http import QueryDict
from tastypie.exceptions import BadRequest
from tastypie.paginator import Paginator

logger = logging.getLogger(__name__)


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

        return self._generate_uri(limit, offset-limit)

    def get_next(self, limit, offset, count):
        """
        Always generate the next URL even if there may be no records.
        """
        return self._generate_uri(limit, offset+limit)

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


def make_cursor_paginator(get_cursor_params, get_object_id):
    """Create a cursor paginator for a tastypie API.

    The API must return consistently ordered results between requests:
      e.g. order_by("date", "id")

    The current implementation does not support use cases where all objects in the batch have
    the same filter parameter value (see TestMessagingEventResource.test_cursor_stuck_in_loop).

    :param get_cursor_params: A function that takes the last object in the batch
        and returns filter parameters for that object. A second parameter is passed
        to indicate the direction of sorting. e.g.

        def get_cursor_params(object, ascending_order):
            param = "date.gte" if ascending_order else "date.lte"
            return {param: event.date.isoformat()}

    :param get_object_id: Function to get the ID of an object. This must be formatted as it would
        be in the cursor (urlencoded). e.g.

        def get_object_id(object):
            return str(object.id)
    """

    class _CursorPaginator(Paginator):
        last_id_param = "last_object_id"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if "cursor" in self.request_data:
                params_string = b64decode(self.request_data['cursor']).decode('utf-8')
                self.cursor_params = QueryDict(params_string).dict()
            else:
                self.cursor_params = None

        def page(self):
            self.check_ordering()

            limit = self.get_limit()
            objects = self.get_objects(limit)
            meta = {'limit': limit, 'next': self.get_cursor(limit, objects)}

            return {
                self.collection_name: objects,
                'meta': meta,
            }

        def get_objects(self, limit):
            """Get the list of objects to return. For pages > 1 this will
            skip the first object in the page if it was present in the previous
            page (as encoded in the cursor)"""
            if self.cursor_params:
                objects = list(self.get_slice(limit + 1, 0))
                last_id = self.cursor_params.get(self.last_id_param, None)
                if last_id and get_object_id(objects[0]) == last_id:
                    logger.debug(f"Skipping first object in API response: {last_id}")
                    objects = objects[1:]  # remove the first object since it was in the last page
                else:
                    logger.debug(f"Dropping last object in API response to keep page size consistent")
                    objects = objects[:-1]
            else:
                logger.debug("no cursor, returning normal page")
                objects = list(self.get_slice(limit, 0))

            return objects

        def check_ordering(self):
            """Make sure the ordering is not changing between pages"""
            if self.cursor_params and "order_by" in self.request_data:
                request_order_by = self.request_data["order_by"]
                cursor_order_by = self.cursor_params.get("order_by")
                if request_order_by != cursor_order_by:
                    raise BadRequest("Changing ordering during pagination is not supported")

        def get_cursor(self, limit, objects):
            """Generate the 'cursor' parameter which includes all query params from the current
            request excluding 'limit' as well as:
              - filter parameter for the next page e.g. date.gte = last date
              - ID of the last object in the current page to allow skipping it in the next page
            """
            if self.resource_uri is None:
                return None

            if not objects:
                return None

            ascending_order = True
            order_by = None
            if "order_by" in self.request_data:
                order_by = self.request_data["order_by"]
                if order_by.startswith("-"):
                    ascending_order = False

            last_object = objects[-1]

            cursor_params = get_cursor_params(last_object, ascending_order)
            # add the ID of the last item so we can remove it from the next page if necessary
            cursor_params[self.last_id_param] = get_object_id(last_object)

            request_params = {}
            for k, v in self.request_data.items():
                if isinstance(v, str):
                    request_params[k] = v.encode('utf-8')
                else:
                    request_params[k] = v

            if 'limit' in request_params:
                del request_params['limit']
            request_params.update(cursor_params)
            encoded_params = urlencode(request_params)

            cursor = {'cursor': b64encode(encoded_params.encode('utf-8')), 'limit': limit}
            if order_by:
                cursor["order_by"] = order_by

            return '%s?%s' % (
                self.resource_uri,
                urlencode(cursor)
            )

    return _CursorPaginator

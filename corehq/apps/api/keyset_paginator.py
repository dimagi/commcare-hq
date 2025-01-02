from itertools import islice
from django.conf import settings
from django.http.request import QueryDict
from tastypie.exceptions import BadRequest
from tastypie.paginator import Paginator
from urllib.parse import urlencode


class KeysetPaginator(Paginator):
    '''
    An alternate paginator meant to support paginating by keyset rather than by index/offset.
    `objects` is expected to represent a query object that exposes an `.execute(limit)`
        method that returns an iterable, and a `get_query_params(object)` method to retrieve the parameters
        for the next query
    Because keyset pagination does not efficiently handle slicing or offset operations,
    these methods have been intentionally disabled
    '''
    def __init__(self, request_data, objects,
                 resource_uri=None, limit=None, max_limit=1000, collection_name='objects'):
        super().__init__(
            request_data,
            objects,
            resource_uri=resource_uri,
            limit=limit,
            max_limit=max_limit,
            collection_name=collection_name
        )
        self.max_page_size = self.max_limit

    def get_offset(self):
        raise NotImplementedError()

    def get_slice(self, limit, offset):
        raise NotImplementedError()

    def get_count(self):
        raise NotImplementedError()

    def get_previous(self, limit, offset):
        raise NotImplementedError()

    def get_next(self, **next_params):
        if self.resource_uri is None:
            return None

        if isinstance(self.request_data, QueryDict):
            # Because QueryDict allows multiple values for the same key, we need to remove existing values
            # prior to updating
            request_params = self.request_data.copy()
            for key in next_params:
                if key in request_params:
                    del request_params[key]

            request_params.update(next_params)
            encoded_params = request_params.urlencode()
        else:
            request_params = {}
            for k, v in self.request_data.items():
                if isinstance(v, str):
                    request_params[k] = v.encode('utf-8')
                else:
                    request_params[k] = v

            request_params.update(next_params)
            encoded_params = urlencode(request_params)

        return '%s?%s' % (
            self.resource_uri,
            encoded_params
        )

    def get_page_size(self):
        page_size = self.request_data.get('page_size', None)

        if page_size is None:
            page_size = getattr(settings, 'API_LIMIT_PER_PAGE', 20)

        try:
            page_size = int(page_size)
        except ValueError:
            raise BadRequest("Invalid limit '%s' provided. Please provide a positive integer." % page_size)

        if page_size < 0:
            raise BadRequest("Invalid limit '%s' provided. Please provide a positive integer >= 0." % page_size)

        if self.max_page_size and (not page_size or page_size > self.max_page_size):
            # If it's more than the max, we're only going to return the max.
            # This is to prevent excessive DB (or other) load.
            return self.max_page_size

        return page_size

    def get_limit(self):
        limit = self.request_data.get('limit', 0)

        try:
            limit = int(limit)
        except ValueError:
            raise BadRequest("Invalid limit '%s' provided. Please provide a positive integer." % limit)

        if limit < 0:
            raise BadRequest("Invalid limit '%s' provided. Please provide a positive integer >= 0." % limit)
        return limit

    def page(self):
        """
        Generates all pertinent data about the requested page.
        """
        limit = self.get_limit()
        page_size = self.get_page_size()
        upper_bound = None
        remaining = 0

        # If we have a page size and no limit was provided, or the page size is less than the limit...
        if page_size and ((not limit) or (limit and page_size < limit)):
            # Fetch 1 more record than requested to allow us to determine if further queries will be needed
            upper_bound = page_size
            it = iter(self.objects.execute(limit=page_size + 1))
            remaining = limit - page_size if limit else 0
        else:
            upper_bound = limit if limit else None
            it = iter(self.objects.execute(limit=upper_bound))

        objects = list(islice(it, upper_bound))

        try:
            next(it)
            has_more = True
        except StopIteration:
            has_more = False

        meta = {
            'limit': limit,
        }

        if upper_bound and has_more:
            last_fetched = objects[-1]
            next_page_params = self.objects.get_query_params(last_fetched)
            if remaining:
                next_page_params['limit'] = remaining
            meta['next'] = self.get_next(**next_page_params)

        return {
            self.collection_name: objects,
            'meta': meta,
        }

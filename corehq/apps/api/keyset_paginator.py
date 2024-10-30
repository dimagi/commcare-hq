from itertools import islice
from django.http.request import QueryDict
from urllib.parse import urlencode
from tastypie.paginator import Paginator


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

    def get_offset(self):
        raise NotImplementedError()

    def get_slice(self, limit, offset):
        raise NotImplementedError()

    def get_count(self):
        raise NotImplementedError()

    def get_previous(self, limit, offset):
        raise NotImplementedError()

    def get_next(self, limit, **next_params):
        return self._generate_uri(limit, **next_params)

    def _generate_uri(self, limit, **next_params):
        if self.resource_uri is None:
            return None

        if isinstance(self.request_data, QueryDict):
            # Because QueryDict allows multiple values for the same key, we need to remove existing values
            # prior to updating
            request_params = self.request_data.copy()
            if 'limit' in request_params:
                del request_params['limit']
            for key in next_params:
                if key in request_params:
                    del request_params[key]

            request_params.update({'limit': str(limit), **next_params})
            encoded_params = request_params.urlencode()
        else:
            request_params = {}
            for k, v in self.request_data.items():
                if isinstance(v, str):
                    request_params[k] = v.encode('utf-8')
                else:
                    request_params[k] = v

            request_params.update({'limit': limit, **next_params})
            encoded_params = urlencode(request_params)

        return '%s?%s' % (
            self.resource_uri,
            encoded_params
        )

    def page(self):
        """
        Generates all pertinent data about the requested page.
        """
        limit = self.get_limit()
        padded_limit = limit + 1 if limit else limit
        # Fetch 1 more record than requested to allow us to determine if further queries will be needed
        it = iter(self.objects.execute(limit=padded_limit))
        objects = list(islice(it, limit))

        try:
            next(it)
            has_more = True
        except StopIteration:
            has_more = False

        meta = {
            'limit': limit,
        }

        if limit and has_more:
            last_fetched = objects[-1]
            next_page_params = self.objects.get_query_params(last_fetched)
            meta['next'] = self.get_next(limit, **next_page_params)

        return {
            self.collection_name: objects,
            'meta': meta,
        }


class PageableQueryInterface:
    def execute(limit=None):
        '''
        Should return an iterable that exposes a `.get_query_params()` method
        '''
        raise NotImplementedError()

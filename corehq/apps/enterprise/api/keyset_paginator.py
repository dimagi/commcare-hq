from itertools import islice
from django.http.request import QueryDict
from urllib.parse import urlencode
from tastypie.paginator import Paginator


class KeysetPaginator(Paginator):
    def __init__(self, request_data, objects,
                 resource_uri=None, limit=None, max_limit=1000, collection_name='objects'):
        'objects is expected to be an iterator'
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

        objects = list(islice(self.objects, limit if limit else None))
        meta = {
            'limit': limit,
        }

        if limit:
            next_params = self.objects.get_next_query_params()
            if next_params:
                meta['next'] = self.get_next(limit, **next_params)

        return {
            self.collection_name: objects,
            'meta': meta,
        }

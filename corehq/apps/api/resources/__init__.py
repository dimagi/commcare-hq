from tastypie.resources import Resource
from tastypie.exceptions import InvalidSortError


class dict_object(object):
    def __init__(self, dict):
        self.dict = dict

    def __getattr__(self, item):
        return self.dict[item]

    def __repr__(self):
        return 'dict_object(%r)' % self.dict


class JsonResource(Resource):
    """
    This can be extended to default to json formatting. 
    """
    # This exists in addition to the mixin since the order of the class
    # definitions actually matters

    def determine_format(self, request):
        format = super(JsonResource, self).determine_format(request)

        # Tastypie does _not_ support text/html but also does not raise the appropriate UnsupportedFormat exception
        # for all other unsupported formats, Tastypie has correct behavior, so we only hack around this one.
        if format == 'text/html':
            format = 'application/json'

        return format


class SimpleSortableResourceMixin(object):
    '''
    In toastdriven/tastypie the apply_sorting method is moderately Django-specific so it is not
    implemented in the Resource class but only in the ModelResource class. This is a
    version that is simplified to only support direct field ordering (none of Django's fancy `__` field access)

    This can only be mixed in to a resource that passes `obj_list` with type

      order_by :: (*str) -> self.__class__

    and should also have a meta field `ordering` that specifies the allowed fields

      _meta :: [str]
    
    '''

    def apply_sorting(self, obj_list, options=None):
        if options is None:
            options = {}

        if 'order_by' not in options:
            return obj_list

        order_by = options.getlist('order_by')
        order_by_args = []
        for field in order_by:
            if field.startswith('-'):
                order = '-'
                field_name = field[1:]
            else:
                order = ''
                field_name = field

            # Map the field back to the actual attribute
            if not field_name in self.fields:
                raise InvalidSortError("No matching '%s' field for ordering on." % field_name)

            if not field_name in self._meta.ordering:
                raise InvalidSortError("The '%s' field does not allow ordering." % field_name)

            if self.fields[field_name].attribute is None:
                raise InvalidSortError("The '%s' field has no 'attribute' for ordering with." % field_name)

            order_by_args.append("%s%s" % (order, self.fields[field_name].attribute))

        return obj_list.order_by(*order_by_args)


class DomainSpecificResourceMixin(object):
    def get_list(self, request, **kwargs):
        """
        Exactly copied from https://github.com/toastdriven/django-tastypie/blob/v0.9.14/tastypie/resources.py#L1262
        (BSD licensed) and modified to pass the kwargs to `get_resource_list_uri`
        (tracked by https://github.com/toastdriven/django-tastypie/pull/815)
        """
        # TODO: Uncached for now. Invalidation that works for everyone may be
        #       impossible.
        base_bundle = self.build_bundle(request=request)
        objects = self.obj_get_list(bundle=base_bundle, **self.remove_api_resource_names(kwargs))
        sorted_objects = self.apply_sorting(objects, options=request.GET)
        
        paginator = self._meta.paginator_class(request.GET, sorted_objects, resource_uri=self.get_resource_list_uri(request, kwargs), limit=self._meta.limit, max_limit=self._meta.max_limit, collection_name=self._meta.collection_name)
        to_be_serialized = paginator.page()

        # Dehydrate the bundles in preparation for serialization.
        bundles = []

        for obj in to_be_serialized[self._meta.collection_name]:
            bundle = self.build_bundle(obj=obj, request=request)
            bundles.append(self.full_dehydrate(bundle))

        to_be_serialized[self._meta.collection_name] = bundles
        to_be_serialized = self.alter_list_data_to_serialize(request, to_be_serialized)
        return self.create_response(request, to_be_serialized)

    def get_resource_list_uri(self, request=None, **kwargs):
        """
        Exactly copied from https://github.com/toastdriven/django-tastypie/blob/v0.9.11/tastypie/resources.py#L601
        (BSD licensed) and modified to use the kwargs.

        (v0.9.14 combines get_resource_list_uri and get_resource_uri; this re-separates them to keep things simpler)
        """
        kwargs = dict(kwargs)
        kwargs['resource_name'] = self._meta.resource_name

        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name
            
        try:
            return self._build_reverse_url("api_dispatch_list", kwargs=kwargs)
        except NoReverseMatch:
            return None

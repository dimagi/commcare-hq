import json

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.urls import NoReverseMatch, include, re_path

from tastypie import http
from tastypie.exceptions import BadRequest, ImmediateHttpResponse, InvalidSortError
from tastypie.resources import Resource, convert_post_to_patch
from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.api.cors import add_cors_headers_to_response
from corehq.apps.api.util import get_obj
from corehq.apps.users.util import is_dimagi_email


class DictObject(object):

    def __init__(self, dict=None):
        self._data = dict or {}

    def __getattr__(self, item):
        return self._data.get(item, None)

    def __repr__(self):
        return 'DictObject(%r)' % self._data


def build_content_type(format, encoding='utf-8'):
    if 'charset' in format:
        return format

    return "%s; charset=%s" % (format, encoding)


class JsonResourceMixin(object):
    """
    This can be extended to default to json formatting.
    """
    # This exists in addition to the mixin since the order of the class
    # definitions actually matters

    def create_response(self, request, data, response_class=HttpResponse, **response_kwargs):
        # overridden so we can specify a utf-8 charset
        # http://stackoverflow.com/questions/17280513/tastypie-json-header-to-use-utf-8
        desired_format = self.determine_format(request)
        serialized = self.serialize(request, data, desired_format)
        return response_class(content=serialized, content_type=build_content_type(desired_format),
                              **response_kwargs)

    def determine_format(self, request):
        format = super(JsonResourceMixin, self).determine_format(request)

        # Tastypie does _not_ support text/html but also does not raise the appropriate UnsupportedFormat exception
        # for all other unsupported formats, Tastypie has correct behavior, so we only hack around this one.
        if format == 'text/html':
            format = 'application/json'

        return format


class CorsResourceMixin(object):
    """
    Mixin implementing CORS
    """

    def create_response(self, *args, **kwargs):
        response = super(CorsResourceMixin, self).create_response(*args, **kwargs)
        return add_cors_headers_to_response(response)

    def method_check(self, request, allowed=None):
        if allowed is None:
            allowed = []

        request_method = request.method.lower()
        allows = ', '.join([x.upper() for x in allowed if x])
        if request_method == 'options':
            response = HttpResponse(allows)
            add_cors_headers_to_response(response, allows)
            response['Allow'] = allows
            raise ImmediateHttpResponse(response=response)

        if request_method not in allowed:
            response = http.HttpMethodNotAllowed(allows)
            response['Allow'] = allows
            raise ImmediateHttpResponse(response=response)

        return request_method


class ApiVersioningMixin:
    def __init__(self, api_name=None):
        super().__init__(api_name)
        # Tastypie sets `api_name` on `_meta`, which is a singleton, so if a
        # resource registered multiple times, each instances uses the
        # `api_name` that came last. This approach works with multiple versions
        self.api_name = api_name or self._meta.api_name

    @property
    def urls(self):
        # Old way of doing things, in line with tastypie's versioning scheme
        return [
            re_path(r"^(?P<resource_name>%s)/" % (self._meta.resource_name), include(self._get_urls()))
        ]

    @classmethod
    def get_urlpattern(cls, version):
        # Newer URL pattern, allows for versioning per resource
        resource = cls(api_name=version)
        return re_path(
            r"^(?P<resource_name>%s)/(?P<api_name>%s)/" % (resource._meta.resource_name, version),
            include(resource._get_urls()),
        )

    def _get_urls(self):
        return self.prepend_urls() + [
            re_path(r"^$", self.wrap_view('dispatch_list'), name="api_dispatch_list"),
            re_path(r"^schema/$", self.wrap_view('get_schema'), name="api_get_schema"),
            re_path(r"^set/(?P<%s_list>.*?)/$" % (self._meta.detail_uri_name),
                    self.wrap_view('get_multiple'), name="api_get_multiple"),
            re_path(r"^(?P<%s>.*?)/$" % (self._meta.detail_uri_name),
                    self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        ]


class HqBaseResource(ApiVersioningMixin, CorsResourceMixin, JsonResourceMixin, Resource):
    """
    Convenience class to allow easy adjustment of API resource base classes.
    """

    def dispatch(self, request_type, request, **kwargs):
        if toggles.API_BLACKLIST.enabled_for_request(request):
            msg = ("API access has been temporarily cut off due to too many "
                   "requests.  To re-enable, please contact support.")
            raise ImmediateHttpResponse(HttpResponse(
                json.dumps({"error": msg}),
                content_type="application/json",
                status=401))
        if request.user.is_superuser or domain_has_privilege(request.domain, self.get_required_privilege()):
            if isinstance(self, DomainSpecificResourceMixin):
                track_workflow(request.user.username, "API Request", properties={
                    'domain': request.domain,
                    'is_dimagi': is_dimagi_email(request.user.username),
                })
            return super(HqBaseResource, self).dispatch(request_type, request, **kwargs)
        else:
            raise ImmediateHttpResponse(HttpResponse(
                json.dumps({"error": "Your current subscription does not have access to this feature"}),
                content_type="application/json",
                status=401))

    def alter_deserialized_detail_data(self, request, data):
        """Provide a hook for data validation

        Subclasses may implement ``validate_deserialized_data`` that
        raises ``django.core.exceptions.ValidationError`` if the submitted
        data is not valid. This is designed to work conveniently with
        ``corehq.util.validation.JSONSchemaValidator``.
        """
        data = super().alter_deserialized_detail_data(request, data)
        if hasattr(self, "validate_deserialized_data"):
            try:
                self.validate_deserialized_data(data)
            except ValidationError as error:
                raise ImmediateHttpResponse(self.error_response(request, error.messages))
        return data

    def get_required_privilege(self):
        return privileges.API_ACCESS

    def patch_list_replica(self, create_or_update_object, request=None, obj_limit=None, **kwargs):
        """
        Exactly copied from https://github.com/toastdriven/django-tastypie/blob/v0.9.14/tastypie/resources.py#L1466
        (BSD licensed) and modified to call custom method `create_or_update_object` on each bundle
        """
        request = convert_post_to_patch(request)
        deserialized = self.deserialize(request, request.body,
                                        format=request.META.get('CONTENT_TYPE', 'application/json'))

        collection_name = self._meta.collection_name
        if collection_name not in deserialized:
            raise BadRequest("Invalid data sent: missing '%s'" % collection_name)

        if len(deserialized[collection_name]) and 'put' not in self._meta.detail_allowed_methods:
            raise ImmediateHttpResponse(response=http.HttpMethodNotAllowed())

        bundles_seen = []
        status = http.HttpAccepted

        if obj_limit and obj_limit < len(deserialized[collection_name]):
            raise BadRequest("Object count exceeds limit for PATCH method.")

        for data in deserialized[collection_name]:
            data = self.alter_deserialized_detail_data(request, data)
            bundle = self.build_bundle(data=data, request=request)
            try:
                create_or_update_object(bundle=bundle, **self.remove_api_resource_names(kwargs))
            except AssertionError as e:
                status = http.HttpBadRequest
                bundle.data['_id'] = str(e)
            bundles_seen.append(bundle)

        to_be_serialized = [bundle.data['_id'] for bundle in bundles_seen]
        return self.create_response(request, to_be_serialized, response_class=status)


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
            if field_name not in self.fields:
                raise InvalidSortError("No matching '%s' field for ordering on." % field_name)

            if field_name not in self._meta.ordering:
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

        paginator = self._meta.paginator_class(request.GET, sorted_objects,
                                               resource_uri=self.get_resource_list_uri(request, kwargs),
                                               limit=self._meta.limit, max_limit=self._meta.max_limit,
                                               collection_name=self._meta.collection_name)
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

        (v0.9.14 combines get_resource_list_uri and get_resource_uri; this re-separates them to keep
        things simpler)
        """
        kwargs = dict(kwargs)
        kwargs['resource_name'] = self._meta.resource_name

        if self.api_name is not None:
            kwargs['api_name'] = self.api_name

        try:
            return self._build_reverse_url("api_dispatch_list", kwargs=kwargs)
        except NoReverseMatch:
            return None


class CouchResourceMixin(object):

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj)._id
        }

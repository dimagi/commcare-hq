from django.core.exceptions import ObjectDoesNotExist
from corehq.apps.reports.api import ReportApiSource
from tastypie import fields
from tastypie.bundle import Bundle
from corehq.apps.api.resources import JsonResource
from corehq.apps.api.resources.v0_1 import CustomResourceMeta


class DetailURIResource(object):
    def detail_uri_kwargs(self, bundle_or_obj):
        """
        Given a ``Bundle`` or an object (typically a ``Model`` instance),
        it returns the extra kwargs needed to generate a detail URI.
        """
        kwargs = {}

        try:
            if isinstance(bundle_or_obj, Bundle):
                kwargs[self._meta.detail_uri_name] = getattr(bundle_or_obj.obj, self._meta.detail_uri_name)
            else:
                kwargs[self._meta.detail_uri_name] = getattr(bundle_or_obj, self._meta.detail_uri_name)
        except AttributeError:
            pass

        return kwargs


class ReportResource(DetailURIResource, JsonResource):
    meta_fields = ['config', 'indicators', 'indicator_groups']
    type = "report"
    slug = fields.CharField(attribute='slug', readonly=True, unique=True)
    name = fields.CharField(attribute='name', readonly=True)
    config = fields.ListField(attribute='config_meta', readonly=True)
    indicators = fields.ListField(attribute='indicators_meta', readonly=True)
    indicator_groups = fields.ListField(attribute='indicator_groups_meta', readonly=True, null=True)
    results = fields.ListField(attribute='get_results', readonly=True, null=True)

    def dehydrate(self, bundle):
        full = bundle.request.GET.get('full')

        config_complete = bundle.obj.config_complete

        full = full or not config_complete
        bundle.data.update(bundle.obj.api_meta(full=full))

        if not full:
            for f in self.meta_fields:
                del bundle.data[f]

        if not config_complete:
            del bundle.data['results']

        return bundle

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        slug = kwargs['slug']
        source = self.get_source(slug, bundle.request, domain)
        if not source:
            raise ObjectDoesNotExist("Couldn't find a report which matched slug='%s'." % slug)

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        return self.get_api_sources(bundle.request, domain)

    def get_api_sources(self, request, domain=None):
        # TODO: implement method. See corehq.apps.reports.dispatcher.ReportDispatcher#get_reports
        return []

    def get_source(self, slug, request, domain):
        # TODO: implement method
        return None

    class Meta(CustomResourceMeta):
        object_class = ReportApiSource
        resource_name = 'report'
        detail_uri_name = 'slug'
        allowed_methods = ['get']
        collection_name = 'reports'

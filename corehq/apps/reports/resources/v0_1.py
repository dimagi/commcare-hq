from corehq.apps.reports.api import ReportDataSource
from corehq.apps.users.models import Permissions
from dimagi.utils.web import json_request
from django.core.exceptions import ObjectDoesNotExist
from tastypie import fields
from corehq.apps.api.resources import JsonResource
from corehq.apps.api.resources.v0_1 import CustomResourceMeta, RequirePermissionAuthentication
from corehq.apps.domain.models import Domain
from corehq.apps.reports.commtrack.data_sources import StockStatusDataSource


class ReportResource(JsonResource):
    type = "report"
    slug = fields.CharField(attribute='slug', unique=True, readonly=True)
    results = fields.ListField(attribute='get_data', readonly=True, null=True)

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        slug = kwargs['slug']
        source = self.get_source(slug, bundle.request, domain)
        if not source:
            raise ObjectDoesNotExist("Couldn't find a report which matched slug='%s'." % slug)
        return source

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        return self.get_api_sources(bundle.request, domain)

    def get_api_sources(self, request, domain=None):
        # TODO: implement method. See corehq.apps.reports.dispatcher.ReportDispatcher#get_reports
        return []

    def get_source(self, slug, request, domain):
        # naive implementation
        domain = Domain.get_by_name(domain)
        if domain.commtrack_enabled:
            if slug == StockStatusDataSource.slug:
                return self._init_data_source(StockStatusDataSource, request, domain)

    def _init_data_source(self, data_source, request, domain):
        config = json_request(request.GET)
        config['domain'] = domain.name
        return data_source(config)

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(Permissions.view_reports)
        object_class = ReportDataSource
        resource_name = 'report'
        detail_uri_name = 'slug'
        allowed_methods = ['get']
        collection_name = 'reports'
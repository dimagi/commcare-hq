from tastypie import fields
from corehq.apps.api.resources.v0_1 import CustomResourceMeta, RequirePermissionAuthentication
from corehq.apps.api.resources import JsonResource
from corehq.apps.reports.api import ReportDataSource
from corehq.apps.users.models import Permissions
from custom.care_pathways.sqldata import GeographySqlData


class GeographyResource(JsonResource):
    type = "geography"
    lvl_1 = fields.CharField(attribute='lvl_1', unique=True, readonly=True, default='')
    lvl_2 = fields.CharField(attribute='lvl_2', unique=True, readonly=True, default='')
    lvl_3 = fields.CharField(attribute='lvl_3', unique=True, readonly=True, default='')
    lvl_4 = fields.CharField(attribute='lvl_4', unique=True, readonly=True, default='')
    lvl_5 = fields.CharField(attribute='lvl_5', unique=True, readonly=True, default='')
    results = fields.ListField(attribute='get_data', readonly=True, null=True)

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        parent_id = bundle.request.GET['parent_id']
        (level, name) = parent_id.split('__') if '__' in parent_id else (None, None)
        if level:
            return GeographySqlData(domain, level=level, name=name).data.items()
        else:
            return GeographySqlData(domain, level=bundle.request.GET['parent_ref_name']).data.items()

    def dehydrate(self, bundle):
        bundle.data.update(bundle.obj[1])
        return bundle.data

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(Permissions.view_reports)
        object_class = ReportDataSource
        resource_name = 'geography'
        detail_uri_name = 'slug'
        allowed_methods = ['get']
        collection_name = 'objects'

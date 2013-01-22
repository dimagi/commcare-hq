from tastypie import fields as tp_f
from corehq.apps.api.resources import JsonResource
from corehq.apps.api.resources.v0_1 import CustomResourceMeta
from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType

def convert_fdt(fdi):
    fdt = FixtureDataType.get(fdi.data_type_id)
    fdi.fixture_type = fdt.tag
    return fdi

class FixtureResource(JsonResource):
    type = "fixture"
    fields = tp_f.DictField(attribute='fields', readonly=True, unique=True)
    fixture_type = tp_f.CharField(attribute='fixture_type', readonly=True)
    uuid = tp_f.CharField(attribute='_id', readonly=True, unique=True)

    def obj_get(self, request, **kwargs):
        return convert_fdt(get_object_or_not_exist(FixtureDataItem, kwargs['pk'], kwargs['domain']))

    def obj_get_list(self, request, **kwargs):
        domain = kwargs['domain']
        parent_id = request.GET.get("parent_id", None)
        parent_ref_name = request.GET.get("parent_ref_name", None)
        references = request.GET.get("references", None)
        child_type = request.GET.get("child_type", None)
        type_id = request.GET.get("fixture_type_id", None)
        type_tag = request.GET.get("fixture_type", None)

        if parent_id and parent_ref_name and child_type and references:
            parent_fdi = FixtureDataItem.get(parent_id)
            fdis = list(FixtureDataItem.by_field_value(domain, child_type, parent_ref_name, parent_fdi.fields['id']))
        elif type_id or type_tag:
            type_id = type_id or FixtureDataType.by_domain_tag(domain, type_tag).one()
            fdis = list(FixtureDataItem.by_data_type(domain, type_id))
        else:
            fdis = list(FixtureDataItem.by_domain(domain))

        return [convert_fdt(fdi) for fdi in fdis] or []

    class Meta(CustomResourceMeta):
        resource_name = 'fixture'
        limit = 0
from couchdbkit.exceptions import ResourceNotFound
from tastypie import fields
from tastypie.exceptions import NotFound
from tastypie.resources import Resource

from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.resources.v0_4 import (
    BaseApplicationResource,
    XFormInstanceResource,
)
from corehq.apps.api.resources.v0_5 import DoesNothingPaginator
from corehq.apps.app_manager.app_schemas.case_properties import (
    get_all_case_properties_for_case_type,
)
from corehq.apps.app_manager.models import Application
from corehq.apps.export.system_properties import MAIN_FORM_TABLE_PROPERTIES
from corehq.apps.zapier.util import remove_advanced_fields


class ZapierXFormInstanceResource(XFormInstanceResource):

    def dehydrate(self, bundle):
        remove_advanced_fields(bundle.data)
        return bundle


class ZapierApplicationResource(BaseApplicationResource):
    """
    A stripped down application resource that just returns IDs and Names
    """
    id = fields.CharField(attribute='_id')
    name = fields.CharField(attribute='name')


class CustomField(object):
    """
    Custom field object used for triggers and actions in Zapier.
    """

    def __init__(self, initial=None):
        initial = initial or {}
        self.type = initial.get('type', '')
        self.key = initial.get('key', '')
        self.label = initial.get('label', '')
        self.help_text = initial.get('help_text', '')

    def get_content(self):
        return {"type": self.type, "key": self.key, "label": self.label, "help_text": self.help_text}


class BaseZapierCustomFieldResource(Resource):
    type = fields.CharField(attribute='type')
    key = fields.CharField(attribute='key')
    label = fields.CharField(attribute='label', null=True, blank=True)
    help_text = fields.CharField(attribute='help_text', default='', null=True, blank=True)

    def _build_key(self, hashtag_value):
        return hashtag_value.lstrip('#').replace('/', '__')

    def _build_label(self, label):
        return label.replace('_', ' ').replace('-', ' ').lstrip().rstrip().capitalize()

    def _has_default_label(self, question):
        return question['label'] == question['hashtagValue']

    def obj_get_list(self, bundle, **kwargs):
        raise NotImplementedError

    class Meta(CustomResourceMeta):
        object_class = CustomField
        include_resource_uri = False
        paginator_class = DoesNothingPaginator
        allowed_methods = ['get']


class ZapierCustomTriggerFieldFormResource(BaseZapierCustomFieldResource):
    """
    Generates custom trigger field labels for forms
    """

    def obj_get_list(self, bundle, **kwargs):
        """
            https://zapier.com/developer/documentation/v2/trigger-fields-custom/
            Zapier custom fields allow to show default form properties, even if there are no forms submitted.
            It also allows to assign label to json property.
            Format of custom field:
            {
                "type": "unicode",
                "key": "json_key",
                "label": "Label", // optional
                "help_text": "Helps to explain things to users." // optional
            }
        """
        application_id = bundle.request.GET.get('application_id')
        xmlns = bundle.request.GET.get('xmlns')
        if not application_id or not xmlns:
            return []

        try:
            app = Application.get(application_id)
        except ResourceNotFound:
            raise NotFound

        custom_fields = []

        for idx, question in enumerate(app.get_questions(xmlns)):
            if self._has_default_label(question):
                label = question['label'].split('/')[-1]
            else:
                label = question['label']

            custom_fields.append(CustomField(
                dict(
                    type='unicode',
                    key=self._build_key(question['hashtagValue']),
                    label=label
                )
            ))

        for form_property in MAIN_FORM_TABLE_PROPERTIES:
            if form_property.is_advanced or form_property.item.transform:
                continue
            custom_fields.append(CustomField(
                dict(
                    type='unicode',
                    key='__'.join([node.name for node in form_property.item.path]),
                    label=form_property.label,
                    help_text=form_property.help_text
                )
            ))
        return custom_fields

    class Meta(BaseZapierCustomFieldResource.Meta):
        resource_name = 'custom_fields'


# Map between keys and labels for general case properties (properties that every case has)
CASE_PROPERTIES = {
    "date_closed": "Date closed",
    "date_modified": "Date modified",
    "case_id": "Case ID",
    "resource_uri": "Resource URI",
    "user_id": "User ID",
    "xform_ids": "XForm IDs",
    "properties__case_name": "Case name",
    "properties__case_type": "Case type",
    "properties__owner_id": "Owner ID",
    "properties__date_opened": "Date opened",
    "properties__external_id": "External ID",
    "properties__type": "Type",
}


class ZapierCustomFieldCaseResource(BaseZapierCustomFieldResource):
    """
    Generates custom trigger field labels for cases
    """

    def obj_get_list(self, bundle, **kwargs):

        custom_fields = []
        domain = bundle.request.GET.get('domain')
        case_type = bundle.request.GET.get('case_type')

        if not domain or not case_type:
            return []

        props = get_all_case_properties_for_case_type(domain, case_type)
        for prop in props:
            custom_fields.append(CustomField(
                dict(
                    type='unicode',
                    key="properties__" + prop,
                    label=self._build_label(prop)
                )
            ))
        for case_prop, case_prop_zapier_name in CASE_PROPERTIES.items():
            custom_fields.append(CustomField(
                dict(
                    type='unicode',
                    key=case_prop,
                    label=case_prop_zapier_name
                )
            ))

        return custom_fields

    class Meta(BaseZapierCustomFieldResource.Meta):
        resource_name = 'custom_fields_case'


class ZapierCustomActionFieldCaseResource(BaseZapierCustomFieldResource):
    """
        Generates custom action fields for updating or creating a case.  When creating a case, users must provide
        a new case name, as well as optionally providing values for the case properties.  When updating a case,
        users must provide a case id, as well as optionally providing new values for the case properties.
    """
    def obj_get_list(self, bundle, **kwargs):
        custom_fields = []
        domain = bundle.request.GET.get('domain')
        case_type = bundle.request.GET.get('case_type')
        create = bundle.request.GET.get('create')

        if not domain or not case_type:
            return []

        custom_fields.append(CustomField(
            dict(
                type='unicode',
                key='case_name',
                label='Case name'
            )
        ))

        if create == "False":
            custom_fields.append(CustomField(
                dict(
                    type='unicode',
                    key='case_id',
                    label='Case ID'
                )
            ))

        for prop in get_all_case_properties_for_case_type(domain, case_type):
            custom_fields.append(CustomField(
                dict(
                    type='unicode',
                    key=prop,
                    label=self._build_label(prop)
                )
            ))

        return custom_fields

    class Meta(BaseZapierCustomFieldResource.Meta):
        resource_name = 'custom_action_fields_case'

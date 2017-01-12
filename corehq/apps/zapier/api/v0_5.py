from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.resources.v0_4 import XFormInstanceResource
from corehq.apps.api.resources.v0_5 import DoesNothingPaginator
from corehq.apps.export.system_properties import MAIN_FORM_TABLE_PROPERTIES
from corehq.apps.zapier.util import remove_advanced_fields
from corehq.apps.app_manager.models import Application


from tastypie.resources import Resource
from tastypie import fields


class ZapierXFormInstanceResource(XFormInstanceResource):

    def dehydrate(self, bundle):
        remove_advanced_fields(bundle.data)
        return bundle


class CustomField(object):

    def __init__(self, initial=None):
        initial = initial or {}
        self.type = initial.get('type', '')
        self.key = initial.get('key', '')
        self.label = initial.get('label', '')
        self.help_text = initial.get('help_text', '')


class ZapierCustomFieldResource(Resource):
    type = fields.CharField(attribute='type')
    key = fields.CharField(attribute='key')
    label = fields.CharField(attribute='label', null=True, blank=True)
    help_text = fields.CharField(attribute='help_text', default='', null=True, blank=True)

    def _build_key(self, hashtag_value):
        return hashtag_value.lstrip('#').replace('/', '__')

    def _has_default_label(self, question):
        return question['label'] == question['hashtagValue']

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

        app = Application.get(application_id)
        form = app.get_form_by_xmlns(xmlns)
        custom_fields = []
        for idx, question in enumerate(form.get_questions(app.langs)):
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
            if form_property.is_advanced:
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

    class Meta(CustomResourceMeta):
        object_class = CustomField
        resource_name = 'custom_fields'
        include_resource_uri = False
        paginator_class = DoesNothingPaginator

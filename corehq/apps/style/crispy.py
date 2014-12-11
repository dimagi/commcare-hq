import re
from bootstrap3_crispy.bootstrap import FormActions as OriginalFormActions
from bootstrap3_crispy.layout import Field as OldField, LayoutObject
from bootstrap3_crispy.utils import render_field
from django.template import Context
from django.template.loader import render_to_string

TEMPLATE_PACK = 'bootstrap3'


def _get_offsets(context):
    label_class = context.get('label_class', '')
    return re.sub(r'(sm|md|lg)-', '\g<1>-offset-', label_class)


class FormActions(OriginalFormActions):
    """Overrides the crispy forms template to include the gray box around
    the form actions.
    """
    template = 'style/crispy/form_actions.html'

    def render(self, form, form_style, context, template_pack=TEMPLATE_PACK):
        html = u''
        for field in self.fields:
            html += render_field(field, form, form_style, context, template_pack=template_pack)
        offsets = _get_offsets(context)
        return render_to_string(self.template, Context({
            'formactions': self,
            'fields_output': html,
            'offsets': offsets,
            'field_class': context.get('field_class', '')
        }))

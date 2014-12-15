from bootstrap3_crispy.bootstrap import FormActions as OriginalFormActions
from bootstrap3_crispy.utils import render_field
from django.template import Context
from django.template.loader import render_to_string

TEMPLATE_PACK = 'bootstrap3'


class FormActions(OriginalFormActions):
    template = 'style/crispy/form_actions.html'

    def render(self, form, form_style, context, template_pack=TEMPLATE_PACK):
        html = u''
        for field in self.fields:
            html += render_field(field, form, form_style, context, template_pack=template_pack)

        return render_to_string(self.template, Context({
            'formactions': self,
            'fields_output': html,
            'label_size': context.get('label_size', 0),
            'field_class': context.get('field_class', '')
        }))

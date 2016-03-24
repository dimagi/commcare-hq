from crispy_forms.bootstrap import AccordionGroup
from crispy_forms.layout import Field
from crispy_forms.utils import get_template_pack


class FieldsetAccordionGroup(AccordionGroup):
    template = "hqwebapp/crispy/layout/fieldset_accordion_group.html"


class HiddenFieldWithErrors(Field):
    template = "hqwebapp/crispy/field/hidden_with_errors.html"


class TextField(Field):
    """
    Layout object.
    Contains text specified in place of the field's normal input.
    """
    template = "hqwebapp/crispy/field/field_with_text.html"

    def __init__(self, field_name, text, *args, **kwargs):
        self.text = text
        super(TextField, self).__init__(field_name, *args, **kwargs)

    def render(self, form, form_style, context, template_pack=None):
        template_pack = template_pack or get_template_pack()
        context.update({
            'field_text': self.text,
        })
        return super(TextField, self).render(form, form_style, context,
                                             template_pack=template_pack)


class ErrorsOnlyField(Field):
    template = 'hqwebapp/crispy/field/errors_only_field.html'

import re
from django.utils.safestring import mark_safe
from crispy_forms.bootstrap import FormActions as OriginalFormActions
from crispy_forms.layout import Field as OldField, LayoutObject
from crispy_forms.utils import render_field, get_template_pack, flatatt
from django.template import Context
from django.template.loader import render_to_string


def _get_offsets(context):
    label_class = context.get('label_class', '')
    return re.sub(r'(sm|md|lg)-', '\g<1>-offset-', label_class)


class FormActions(OriginalFormActions):
    """Overrides the crispy forms template to include the gray box around
    the form actions.
    """
    template = 'style/crispy/form_actions.html'

    def render(self, form, form_style, context, template_pack=None):
        template_pack = template_pack or get_template_pack()
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


class Field(OldField):
    """Overrides the logic behind choosing the offset class for the field to
    actually be responsive (col-lg-offset-*, col-md-offset-*, etc). Also includes
    support for static controls.
    """
    template = 'style/crispy/field.html'

    def __init__(self, *args, **kwargs):
        self.is_static = False
        if 'is_static' in kwargs:
            self.is_static = kwargs.pop('is_static')
        super(Field, self).__init__(*args, **kwargs)

    def render(self, form, form_style, context, template_pack=None):
        template_pack = template_pack or get_template_pack()
        offsets = _get_offsets(context)
        context.update({
            'offsets': offsets,
        })
        return super(Field, self).render(form, form_style, context, template_pack)


class StaticField(LayoutObject):
    template = 'style/crispy/static_field.html'

    def __init__(self, field_label, field_value):
        self.field_label = field_label
        self.field_value = field_value

    def render(self, form, form_style, context, template_pack=None):
        template_pack = template_pack or get_template_pack()
        context.update({
            'field_label': self.field_label,
            'field_value': self.field_value,
        })
        return render_to_string(self.template, context)


class B3MultiField(LayoutObject):
    template = 'style/crispy/multi_field.html'

    def __init__(self, field_label, *fields, **kwargs):
        self.fields = list(fields)
        self.label_html = field_label
        self.flat_attrs = flatatt(kwargs)

    def render(self, form, form_style, context, template_pack=None):
        template_pack = template_pack or get_template_pack()
        html = u''
        for field in self.fields:
            html += render_field(field, form, form_style, context, template_pack=template_pack)
        context.update({
            'label_html': mark_safe(self.label_html),
            'field_html': mark_safe(html),
            'multifield': self,
        })
        return render_to_string(self.template, context)


class CrispyTemplate(object):

    def __init__(self, template, context):
        self.template = template
        self.context = context

    def render(self, form, form_style, context, template_pack=None):
        context.update(self.context)
        return render_to_string(self.template, context)

import re
from contextlib import contextmanager

from django.utils.safestring import mark_safe
from crispy_forms.bootstrap import FormActions as OriginalFormActions, InlineField, AccordionGroup
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
    todo since we forked crispy forms, this class is no longer necessary. http://manage.dimagi.com/default.asp?186372
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


@contextmanager
def edited_classes(context, label_class, field_class):
    original_label_class = context.get('label_class')
    original_field_class = context.get('field_class')
    try:
        context['label_class'] = label_class or context.get('label_class')
        context['field_class'] = field_class or context.get('field_class')
        yield
    finally:
        context['label_class'] = original_label_class
        context['field_class'] = original_field_class


class B3MultiField(LayoutObject):
    template = 'style/crispy/multi_field.html'

    def __init__(self, field_label, *fields, **kwargs):
        self.fields = list(fields)
        self.label_html = field_label
        self.css_class = kwargs.pop('css_class', '')
        self.css_id = kwargs.pop('css_id', '')
        self.field_class = kwargs.pop('field_class', None)
        self.label_class = kwargs.pop('label_class', None)
        self.help_bubble_text = kwargs.pop('help_bubble_text', '')
        self.flat_attrs = flatatt(kwargs)

    def render(self, form, form_style, context, template_pack=None):
        template_pack = template_pack or get_template_pack()
        html = u''

        errors = self._get_errors(form, self.fields)
        if len(errors) > 0:
            self.css_class += " has-error"

        for field in self.fields:
            html += render_field(field, form, form_style, context, template_pack=template_pack)
        context.update({
            'label_html': mark_safe(self.label_html),
            'field_html': mark_safe(html),
            'multifield': self,
            'error_list': errors,
            'help_bubble_text': self.help_bubble_text,
        })

        if not (self.field_class or self.label_class):
            return render_to_string(self.template, context)

        with edited_classes(context, self.label_class, self.field_class):
            rendered_view = render_to_string(self.template, context)
        return rendered_view

    def _get_errors(self, form, fields):
        errors = []
        for field in fields:
            if isinstance(field, OldField) or issubclass(field.__class__, OldField):
                fname = field.fields[0]
                if fname not in form.fields:
                    continue
                error_list = form[fname].errors
                if error_list:
                    errors.extend(error_list)
            else:
                try:
                    errors.extend(self._get_errors(form, field.fields))
                except AttributeError:
                    pass
        return errors


class MultiInlineField(InlineField):
    """
    An InlineField to be used within a B3MultiField.

    (Bootstrap 3 Crispy's InlineField adds the form-group class to
    the field's containing div, which is redundant because
    B3MultiField adds form-group at a higher level, and that makes
    the field not render properly.)
    """
    template = 'style/crispy/multi_inline_field.html'


class CrispyTemplate(object):

    def __init__(self, template, context):
        self.template = template
        self.context = context

    def render(self, form, form_style, context, template_pack=None):
        context.update(self.context)
        return render_to_string(self.template, context)


class FieldWithHelpBubble(Field):
    template = "field_with_help_bubble.html"

    def __init__(self, *args, **kwargs):
        super(FieldWithHelpBubble, self).__init__(*args, **kwargs)
        self.help_bubble_text = kwargs.pop('help_bubble_text')

    def render(self, form, form_style, context, template_pack=None):
        template_pack = template_pack or get_template_pack()
        self.template = "style/crispy/{}/{}".format(template_pack, self.template)
        context.update({
            'help_bubble_text': self.help_bubble_text,
        })
        return super(FieldWithHelpBubble, self).render(form, form_style, context, template_pack=template_pack)


class LinkButton(LayoutObject):
    template = "style/crispy/{template_pack}/link_button.html"

    def __init__(self, button_text, button_url, **kwargs):
        self.button_text = button_text
        self.button_url = button_url

        if not hasattr(self, 'attrs'):
            self.attrs = {}

        if 'css_class' in kwargs:
            if 'class' in self.attrs:
                self.attrs['class'] += " %s" % kwargs.pop('css_class')
            else:
                self.attrs['class'] = kwargs.pop('css_class')

    def render(self, form, form_style, context, template_pack=None):
        template_pack = template_pack or get_template_pack()
        template = self.template.format(template_pack=template_pack)
        context.update({
            'button_text': self.button_text,
            'button_url': self.button_url,
            'button_attrs': flatatt(self.attrs if isinstance(self.attrs, dict) else {}),
        })
        return render_to_string(template, context)


class FieldsetAccordionGroup(AccordionGroup):
    template = "style/crispy/{template_pack}/accordion_group.html"

    def render(self, form, form_style, context, template_pack=None):
        template_pack = template_pack or get_template_pack()
        self.template = self.template.format(template_pack=template_pack)
        return super(FieldsetAccordionGroup, self).render(form, form_style, context, template_pack)


class HiddenFieldWithErrors(Field):
    template = "style/crispy/{template_pack}/hidden_with_errors.html"

    def render(self, form, form_style, context, template_pack=None):
        template_pack = template_pack or get_template_pack()
        self.template = self.template.format(template_pack=template_pack)
        return super(HiddenFieldWithErrors, self).render(form, form_style, context, template_pack)

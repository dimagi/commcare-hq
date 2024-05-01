import re
from contextlib import contextmanager
from django.forms.widgets import DateTimeInput
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import gettext

from crispy_forms.bootstrap import AccordionGroup
from crispy_forms.bootstrap import FormActions as OriginalFormActions
from crispy_forms.bootstrap import InlineField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field
from crispy_forms.layout import LayoutObject
from crispy_forms.utils import flatatt, get_template_pack, render_field

CSS_LABEL_CLASS = 'col-xs-12 col-sm-4 col-md-4 col-lg-2'
CSS_LABEL_CLASS_BOOTSTRAP5 = 'col-xs-12 col-sm-4 col-md-4 col-lg-3'
CSS_FIELD_CLASS = 'col-xs-12 col-sm-8 col-md-8 col-lg-6'
CSS_FIELD_CLASS_BOOTSTRAP5 = 'col-xs-12 col-sm-8 col-md-8 col-lg-9'
CSS_ACTION_CLASS = CSS_FIELD_CLASS + ' col-sm-offset-4 col-md-offset-4 col-lg-offset-2'


class HQFormHelper(FormHelper):
    form_class = 'form form-horizontal'
    label_class = CSS_LABEL_CLASS
    field_class = CSS_FIELD_CLASS

    def __init__(self, *args, **kwargs):
        super(HQFormHelper, self).__init__(*args, **kwargs)
        from corehq.apps.hqwebapp.utils.bootstrap import get_bootstrap_version, BOOTSTRAP_5
        bootstrap_version = get_bootstrap_version()
        use_bootstrap5 = bootstrap_version == BOOTSTRAP_5
        if use_bootstrap5:
            self.label_class = CSS_LABEL_CLASS_BOOTSTRAP5
            self.field_class = CSS_FIELD_CLASS_BOOTSTRAP5

        if 'autocomplete' not in self.attrs:
            self.attrs.update({
                'autocomplete': 'off',
            })


class HQModalFormHelper(FormHelper):
    form_class = 'form form-horizontal'
    label_class = 'col-xs-12 col-sm-3 col-md-3 col-lg-2'
    field_class = 'col-xs-12 col-sm-9 col-md-9 col-lg-6'


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

    def render(self, form, context, template_pack=None, **kwargs):
        template_pack = template_pack or get_template_pack()
        context.update({
            'field_text': self.text,
        })
        return super(TextField, self).render(form, context, template_pack=template_pack, **kwargs)


class ErrorsOnlyField(Field):
    template = 'hqwebapp/crispy/field/errors_only_field.html'


def get_form_action_class():
    """This is only valid for bootstrap 5"""
    return CSS_LABEL_CLASS_BOOTSTRAP5.replace('col', 'offset') + ' ' + CSS_FIELD_CLASS_BOOTSTRAP5


def _get_offsets(context):
    label_class = context.get('label_class', '')
    use_bootstrap5 = context.get('use_bootstrap5')
    return (label_class.replace('col', 'offset') if use_bootstrap5
            else re.sub(r'(xs|sm|md|lg)-', r'\g<1>-offset-', label_class))


class FormActions(OriginalFormActions):
    """Overrides the crispy forms template to include the gray box around
    the form actions.
    """
    template = 'hqwebapp/crispy/form_actions.html'

    def render(self, form, context, template_pack=None, **kwargs):
        template_pack = template_pack or get_template_pack()
        fields_html = ''
        for field in self.fields:
            fields_html += render_field(
                field, form, context,
                template_pack=template_pack,
            )
        fields_html = mark_safe(fields_html)  # nosec: just concatenated safe fields
        offsets = _get_offsets(context)
        context.update({
            'formactions': self,
            'fields_output': fields_html,
            'offsets': offsets,
            'field_class': context.get('field_class', '')
        })
        return render_to_string(self.template, context.flatten())


class StaticField(LayoutObject):
    template = 'hqwebapp/crispy/static_field.html'

    def __init__(self, field_label, field_value):
        self.field_label = field_label
        self.field_value = field_value

    def render(self, form, context, template_pack=None, **kwargs):
        template_pack = template_pack or get_template_pack()
        context.update({
            'field_label': self.field_label,
            'field_value': self.field_value,
        })
        return render_to_string(self.template, context.flatten())


class FormStepNumber(LayoutObject):
    template = 'hqwebapp/crispy/form_step_number.html'

    def __init__(self, step_num, total_steps):
        self.step_label = gettext("Step {} of {}".format(step_num, total_steps))

    def render(self, form, context, template_pack=None, **kwargs):
        context.update({
            'step_label': self.step_label,
        })

        return render_to_string(self.template, context.flatten())


class ValidationMessage(LayoutObject):
    """
    IMPORTANT: DO NOT USE IN BOOTSTRAP 5 VIEWS.
    See bootstrap5/validators.ko and revisit styleguide in
    Organisms > Forms for additional help.
    """
    template = 'hqwebapp/crispy/validation_message.html'

    def __init__(self, ko_observable):
        self.ko_observable = ko_observable

    def render(self, form, context, template_pack=None, **kwargs):
        context.update({
            'ko_observable': self.ko_observable,
        })

        return render_to_string(self.template, context.flatten())


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
    template = 'hqwebapp/crispy/multi_field.html'

    # Because fields will be passed as-is to the HTML,
    # care should be taken to ensure they escape user input appropriately
    def __init__(self, field_label, *fields, **kwargs):
        self.fields = list(fields)
        self.label_html = field_label
        self.css_class = kwargs.pop('css_class', '')
        self.css_id = kwargs.pop('css_id', '')
        self.field_class = kwargs.pop('field_class', None)
        self.label_class = kwargs.pop('label_class', None)
        self.show_row_class = kwargs.pop('show_row_class', True)
        self.required = kwargs.pop('required', False)
        self.help_bubble_text = kwargs.pop('help_bubble_text', '')
        self.flat_attrs = flatatt(kwargs)

    def render(self, form, context, template_pack=None, **kwargs):
        template_pack = template_pack or get_template_pack()

        errors = self._get_errors(form, self.fields)
        if len(errors) > 0:
            self.css_class += " has-error"

        html = ''
        for field in self.fields:
            html += render_field(field, form, context, template_pack=template_pack, **kwargs)
        html = mark_safe(html)  # nosec: this is joining together fields which themselves are safe

        context.update({
            'label_html': self.label_html,
            'field_html': html,
            'multifield': self,
            'error_list': errors,
            'help_bubble_text': self.help_bubble_text,
        })

        context_dict = context.flatten()

        if not (self.field_class or self.label_class):
            return render_to_string(self.template, context_dict)

        with edited_classes(context, self.label_class, self.field_class):
            rendered_view = render_to_string(self.template, context_dict)
        return rendered_view

    def _get_errors(self, form, fields):
        errors = []
        for field in fields:
            if isinstance(field, Field) or issubclass(field.__class__, Field):
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
    template = 'hqwebapp/crispy/multi_inline_field.html'


class CrispyTemplate(object):

    def __init__(self, template, context):
        self.template = template
        self.context = context

    def render(self, form, context, template_pack=None, **kwargs):
        context.update(self.context)
        return render_to_string(self.template, context.flatten())


class FieldWithExtras(Field):
    extra_context = None

    def __init__(self, *args, **kwargs):
        self.extras = {
            extra: kwargs.pop(extra, None) for extra in self.extra_context
        }
        super(FieldWithExtras, self).__init__(*args, **kwargs)

    def render(self, form, context, template_pack=None, **kwargs):
        template_pack = template_pack or get_template_pack()
        context.update(self.extras)
        return super(FieldWithExtras, self).render(form, context, template_pack=template_pack, **kwargs)


class CheckboxField(Field):
    template = "bootstrap3to5/layout/prepended_appended_text.html"


class FieldWithHelpBubble(FieldWithExtras):
    """Add a help bubble after the field label.

    Provide the help text using the `help_bubble_text` kwarg.
    """
    template = "hqwebapp/crispy/field_with_help_bubble.html"
    extra_context = ['help_bubble_text']


class FieldWithAddons(FieldWithExtras):
    """Add 'input-group-addon' divs before / after the input
    element. This is mostly only useful with inputs of type
    'text' and 'select'.

    The addon element must be provided using the `pre_addon`
    and `post_addon` kwargs. The value should be a string or
    'SafeString' (to prevent HTML escaping).

    See the Bootstrap docs for addon examples.
    """
    template = "hqwebapp/crispy/field_with_addons.html"
    extra_context = ['pre_addon', 'post_addon']


class LinkButton(LayoutObject):
    template = "hqwebapp/crispy/link_button.html"

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

    def render(self, form, context, template_pack=None, **kwargs):
        context.update({
            'button_text': self.button_text,
            'button_url': self.button_url,
            'button_attrs': flatatt(self.attrs if isinstance(self.attrs, dict) else {}),
        })
        return render_to_string(self.template, context.flatten())


class B3TextField(Field):

    def __init__(self, field_name, text, *args, **kwargs):
        self.text = text
        super(B3TextField, self).__init__(field_name, *args, **kwargs)
        self.template = 'hqwebapp/crispy/text_field.html'

    def render(self, form, context, template_pack=None, **kwargs):
        context.update({
            'field_text': self.text,
        })
        if hasattr(self, 'wrapper_class'):
            context['wrapper_class'] = self.wrapper_class

        html = ''
        for field in self.fields:
            html += render_field(field, form, context,
                                 template=self.template, attrs=self.attrs,
                                 template_pack=template_pack, **kwargs)
        return html


class FieldsetAccordionGroup(AccordionGroup):
    template = "hqwebapp/crispy/accordion_group.html"


class RadioSelect(Field):
    template = "hqwebapp/crispy/radioselect.html"


class DatetimeLocalWidget(DateTimeInput):
    input_type = "datetime-local"


def make_form_readonly(form):
    if form is None:
        return

    for field in form.fields.keys():
        form.fields[field].widget.attrs['disabled'] = True

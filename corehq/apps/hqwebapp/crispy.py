from crispy_forms.bootstrap import AccordionGroup, InlineField
from crispy_forms.layout import MultiField, Field
from crispy_forms.utils import render_field, get_template_pack
from django.template.loader import render_to_string


class BootstrapMultiField(MultiField):
    template = "hqwebapp/crispy/layout/multifield.html"
    field_template = "hqwebapp/crispy/field/multifield.html"

    def __init__(self, *args, **kwargs):
        super(BootstrapMultiField, self).__init__(*args, **kwargs)
        self.help_bubble_text = None
        if 'help_bubble_text' in kwargs:
            self.help_bubble_text = kwargs.pop('help_bubble_text')

    def render(self, form, form_style, context, template_pack=None):
        template_pack = template_pack or get_template_pack()
        fields_output = u''
        for field in self.fields:
            fields_output += render_field(
                field, form, form_style, context,
                self.field_template, self.label_class, layout_object=self,
                template_pack=template_pack
            )

        errors = self._get_errors(form, self.fields)
        if len(errors) > 0:
            self.css_class += " error"

        context.update({
            'multifield': self,
            'fields_output': fields_output,
            'error_list': errors,
            'help_bubble_text': self.help_bubble_text,
        })
        return render_to_string(self.template, context)

    def _get_errors(self, form, fields):
        errors = []
        for field in fields:
            if isinstance(field, Field) or issubclass(field.__class__, Field):
                fname = field.fields[0]
                error = form[fname].errors
                if error:
                    errors.append(error)
            else:
                try:
                    errors.extend(self._get_errors(form, field.fields))
                except AttributeError:
                    pass
        return errors


class FieldsetAccordionGroup(AccordionGroup):
    template = "hqwebapp/crispy/layout/fieldset_accordion_group.html"


class HiddenFieldWithErrors(Field):
    template = "hqwebapp/crispy/field/hidden_with_errors.html"


class FieldWithHelpBubble(Field):
    template = "hqwebapp/crispy/field/field_with_help_bubble.html"

    def __init__(self, *args, **kwargs):
        super(FieldWithHelpBubble, self).__init__(*args, **kwargs)
        self.help_bubble_text = kwargs.pop('help_bubble_text')

    def render(self, form, form_style, context, template_pack=None):
        template_pack = template_pack or get_template_pack()
        context.update({
            'help_bubble_text': self.help_bubble_text,
        })
        return super(FieldWithHelpBubble, self).render(form, form_style, context, template_pack=template_pack)


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


class InlineColumnField(InlineField):

    def __init__(self, *args, **kwargs):
        self.block_css_class = kwargs.pop('block_css_class')
        super(InlineColumnField, self).__init__(*args, **kwargs)

    def render(self, form, form_style, context, template_pack=None):
        template_pack = template_pack or get_template_pack()
        context.update({
            'block_css_class': self.block_css_class,
        })
        return super(InlineColumnField, self).render(
            form, form_style, context, template_pack=template_pack
        )


class ErrorsOnlyField(Field):
    template = 'hqwebapp/crispy/field/errors_only_field.html'

from crispy_forms.layout import MultiField, TEMPLATE_PACK


class BootstrapMultiField(MultiField):
    template = "hqwebapp/crispy/layout/multifield.html"
    field_template = "hqwebapp/crispy/field/multifield.html"

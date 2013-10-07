from crispy_forms.bootstrap import AccordionGroup
from crispy_forms.layout import MultiField, TEMPLATE_PACK, Field


class BootstrapMultiField(MultiField):
    template = "hqwebapp/crispy/layout/multifield.html"
    field_template = "hqwebapp/crispy/field/multifield.html"


class FieldsetAccordionGroup(AccordionGroup):
    template = "hqwebapp/crispy/layout/fieldset_accordion_group.html"


class HiddenFieldWithErrors(Field):
    template = "hqwebapp/crispy/field/hidden_with_errors.html"

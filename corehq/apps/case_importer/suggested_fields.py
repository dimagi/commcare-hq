from django.utils.translation import ugettext as _
from corehq.apps.case_importer.util import get_case_properties_for_case_type, \
    RESERVED_FIELDS
from dimagi.ext import jsonobject


def get_suggested_case_fields(domain, case_type, exclude=None):
    exclude_fields = set(RESERVED_FIELDS)
    if exclude:
        exclude_fields.update(exclude)
    dynamic_fields = set(get_case_properties_for_case_type(domain, case_type)) - exclude_fields
    return sorted(
        get_special_fields() +
        [FieldSpec(field=field, show_in_menu=True) for field in dynamic_fields],
        key=lambda field_spec: field_spec.field
    )


class FieldSpec(jsonobject.StrictJsonObject):
    field = jsonobject.StringProperty()
    description = jsonobject.StringProperty()
    show_in_menu = jsonobject.BooleanProperty(default=False)
    discoverable = jsonobject.BooleanProperty(default=True)


def get_special_fields():
    return [
        FieldSpec(
            field='name',
            description=_("This field will be used to set the case's name."),
            show_in_menu=True),
        FieldSpec(
            field='owner_name',
            description=_("This field will assign the case to a new owner given by "
                          "Username, Group name, or Organization name."),
        ),
        FieldSpec(
            field='owner_id',
            description=_("This field will assign the case to a new owner given by "
                          "User ID, Group ID, or Organization ID.")),
        FieldSpec(
            field='parent_external_id',
            description=_("This field will assign the case a new parent given by "
                          "the parent case's external_id. "
                          "You must use along with parent_type.")),
        FieldSpec(
            field='parent_id',
            description=_("This field will assign the case a new parent given by "
                          "the parent's Case ID. "
                          "You must use along with parent_type.")),
        FieldSpec(
            field='parent_type',
            description=_("Use to specify the parent's case type. "
                          "Usually used with parent_id or parent_external_id")),
        FieldSpec(
            field='parent_ref',
            description=_("This is a deprecated feature needed for a handful of clients. "
                          "Please do not use unless you know what you are doing")),
        FieldSpec(
            field='close',
            description=_("This field will be used to close cases. "
                          "Any case with 'yes' in this column will be closed.")),
    ]

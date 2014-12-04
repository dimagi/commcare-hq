from couchdbkit.ext.django.schema import (Document, StringProperty,
    BooleanProperty, SchemaListProperty, StringListProperty)
from jsonobject import JsonObject
from django.utils.translation import ugettext as _


CUSTOM_DATA_FIELD_PREFIX = "data-field"


class CustomDataField(JsonObject):
    slug = StringProperty()
    is_required = BooleanProperty()
    label = StringProperty()
    choices = StringListProperty()


class CustomDataFieldsDefinition(Document):
    """
    Per-project user-defined fields such as custom user data.
    """
    field_type = StringProperty()
    base_doc = "CustomDataFieldsDefinition"
    domain = StringProperty()
    fields = SchemaListProperty(CustomDataField)

    @classmethod
    def get_or_create(cls, domain, field_type):
        existing = cls.view(
            'custom_data_fields/by_field_type',
            key=[domain, field_type],
            include_docs=True,
            reduce=False,
            # if there's more than one,
            # it's probably because a few were created at the same time
            # due to a race condition
            # todo: a better solution might be to use locking in this code
            limit=1,
        ).one()

        if existing:
            return existing
        else:
            new = cls(domain=domain, field_type=field_type)
            new.save()
            return new

    # TODO use this in the CustomDataEditor too?
    def get_validator(self, data_field_class):
        """
        Returns a validator to be used in bulk import
        """
        def validate_choices(field, value):
            if field.choices and value and value not in field.choices:
                return _(
                    "'{value}' is not a valid choice for {slug}, the available "
                    "options are: {options}."
                ).format(
                    value=value,
                    slug=field.slug,
                    options=', '.join(field.choices),
                )

        def validate_required(field, value):
            if field.is_required and not value:
                return _(
                    "Cannot create or update a {entity} without "
                    "the required field: {field}."
                ).format(
                    entity=data_field_class.entity_string,
                    field=field.slug
                )

        def validate_custom_fields(custom_fields):
            errors = []
            for field in self.fields:
                value = custom_fields.get(field.slug, None)
                errors.append(validate_required(field, value))
                errors.append(validate_choices(field, value))

            return ' '.join(filter(None, errors))

        return validate_custom_fields

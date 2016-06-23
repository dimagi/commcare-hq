from dimagi.ext.couchdbkit import (Document, StringProperty,
    BooleanProperty, SchemaListProperty, StringListProperty)
from dimagi.ext.jsonobject import JsonObject
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from .dbaccessors import get_by_domain_and_type


CUSTOM_DATA_FIELD_PREFIX = "data-field"
# If mobile-worker is demo, this will be set to value 'demo'
COMMCARE_USER_TYPE_KEY = 'user_type'
COMMCARE_USER_TYPE_DEMO = 'demo'
# This list is used to grandfather in existing data, any new fields should use
# the system prefix defined below
SYSTEM_FIELDS = ("commtrack-supply-point", 'name', 'type', 'owner_id', 'external_id', 'hq_user_id',
                 COMMCARE_USER_TYPE_KEY)
SYSTEM_PREFIX = "commcare"


def validate_reserved_words(slug):
    if slug in SYSTEM_FIELDS:
        raise ValidationError(_('You may not use "{}" as a field name').format(slug))
    for prefix in [SYSTEM_PREFIX, 'xml']:
        if slug and slug.startswith(prefix):
            raise ValidationError(_('Field names may not begin with "{}"').format(prefix))


def is_system_key(slug):
    try:
        validate_reserved_words(slug)
    except ValidationError:
        return True


class CustomDataField(JsonObject):
    slug = StringProperty()
    is_required = BooleanProperty()
    label = StringProperty()
    choices = StringListProperty()
    is_multiple_choice = BooleanProperty(default=False)


class CustomDataFieldsDefinition(Document):
    """
    Per-project user-defined fields such as custom user data.
    """
    field_type = StringProperty()
    base_doc = "CustomDataFieldsDefinition"
    domain = StringProperty()
    fields = SchemaListProperty(CustomDataField)

    def get_fields(self, required_only=False, include_system=True):
        def _is_match(field):
            if ((required_only and not field.is_required)
                    or (not include_system and is_system_key(field.slug))):
                return False
            return True
        return filter(_is_match, self.fields)

    @classmethod
    def get_or_create(cls, domain, field_type):
        # todo: this overrides get_or_create from DocumentBase but with a completely different signature.
        # This method should probably be renamed.
        existing = get_by_domain_and_type(domain, field_type)

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
            if field.choices and value and unicode(value) not in field.choices:
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

    def get_model_and_uncategorized(self, data_dict):
        """
        Splits data_dict into two dictionaries:
        one for data which matches the model and one for data that doesn't
        Does not include reserved fields.
        """
        if not data_dict:
            return {}, {}
        model_data = {}
        uncategorized_data = {}
        slugs = [field.slug for field in self.fields]
        for k, v in data_dict.items():
            if k in slugs:
                model_data[k] = v
            elif is_system_key(k):
                pass
            else:
                uncategorized_data[k] = v

        return model_data, uncategorized_data

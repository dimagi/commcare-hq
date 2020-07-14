import re

from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils.translation import ugettext as _

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    Document,
    SchemaListProperty,
    StringListProperty,
    StringProperty,
)
from dimagi.ext.jsonobject import JsonObject
from dimagi.utils.couch.migration import SyncCouchToSQLMixin, SyncSQLToCouchMixin

from corehq.apps.cachehq.mixins import QuickCachedDocumentMixin

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
    return False


class SQLField(models.Model):
    slug = models.CharField(max_length=127)
    is_required = models.BooleanField(default=False)
    label = models.CharField(max_length=255)
    choices = JSONField(default=list, null=True)
    regex = models.CharField(max_length=127, null=True)
    regex_msg = models.CharField(max_length=255, null=True)
    definition = models.ForeignKey('SQLCustomDataFieldsDefinition', on_delete=models.CASCADE)

    class Meta:
        db_table = "custom_data_fields_field"
        order_with_respect_to = "definition"

    def validate_choices(self, value):
        if self.choices and value and str(value) not in self.choices:
            return _(
                "'{value}' is not a valid choice for {label}. The available "
                "options are: {options}."
            ).format(
                value=value,
                label=self.label,
                options=', '.join(self.choices),
            )

    def validate_regex(self, value):
        if self.regex and value and not re.search(self.regex, value):
            return _("'{value}' is not a valid match for {label}").format(
                value=value, label=self.label)

    def validate_required(self, value):
        if self.is_required and not value:
            return _(
                "{label} is required."
            ).format(
                label=self.label
            )


class CustomDataField(JsonObject):
    slug = StringProperty()
    is_required = BooleanProperty(default=False)
    label = StringProperty(default='')
    choices = StringListProperty()
    regex = StringProperty()
    regex_msg = StringProperty()


class SQLCustomDataFieldsDefinition(SyncSQLToCouchMixin, models.Model):
    field_type = models.CharField(max_length=126)
    domain = models.CharField(max_length=255, null=True)
    couch_id = models.CharField(max_length=126, null=True, db_index=True)

    class Meta:
        db_table = "custom_data_fields_customdatafieldsdefinition"
        unique_together = ('domain', 'field_type')

    @classmethod
    def _migration_get_fields(cls):
        return ["domain", "field_type"]

    def _migration_sync_to_couch(self, couch_obj):
        for field_name in self._migration_get_fields():
            value = getattr(self, field_name)
            setattr(couch_obj, field_name, value)
        couch_obj.fields = [
            CustomDataField(
                slug=field.slug,
                is_required=field.is_required,
                label=field.label,
                choices=field.choices,
                regex=field.regex,
                regex_msg=field.regex_msg,
            ) for field in self.get_fields()
        ]
        couch_obj.save(sync_to_sql=False)

    @classmethod
    def _migration_get_couch_model_class(cls):
        return CustomDataFieldsDefinition

    @classmethod
    def get(cls, domain, field_type):
        return cls.objects.filter(domain=domain, field_type=field_type).first()

    @classmethod
    def get_or_create(cls, domain, field_type):
        existing = cls.get(domain, field_type)
        if existing:
            return existing
        else:
            new = cls(domain=domain, field_type=field_type)
            new.save()
            return new

    # Gets ordered, and optionally filtered, fields
    def get_fields(self, required_only=False, include_system=True):
        def _is_match(field):
            return not (
                (required_only and not field.is_required)
                or (not include_system and is_system_key(field.slug))
            )
        order = self.get_sqlfield_order()
        fields = [SQLField.objects.get(id=o) for o in order]
        return [f for f in fields if _is_match(f)]

    # Note that this does not save
    def set_fields(self, fields):
        self.sqlfield_set.all().delete()
        self.sqlfield_set.set(fields, bulk=False)
        self.set_sqlfield_order([f.id for f in fields])

    def get_validator(self):
        """
        Returns a validator to be used in bulk import
        """
        def validate_custom_fields(custom_fields):
            errors = []
            for field in self.get_fields():
                value = custom_fields.get(field.slug, None)
                errors.append(field.validate_required(value))
                errors.append(field.validate_choices(value))
                errors.append(field.validate_regex(value))
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
        slugs = {field.slug for field in self.sqlfield_set.all()}
        for k, v in data_dict.items():
            if k in slugs:
                model_data[k] = v
            elif is_system_key(k):
                pass
            else:
                uncategorized_data[k] = v

        return model_data, uncategorized_data


class CustomDataFieldsDefinition(SyncCouchToSQLMixin, QuickCachedDocumentMixin, Document):
    """
    Per-project user-defined fields such as custom user data.
    """
    field_type = StringProperty()
    base_doc = "CustomDataFieldsDefinition"
    domain = StringProperty()
    fields = SchemaListProperty(CustomDataField)

    @classmethod
    def _migration_get_fields(cls):
        return ["domain", "field_type"]

    def _migration_sync_to_sql(self, sql_object):
        for field_name in self._migration_get_fields():
            value = getattr(self, field_name)
            setattr(sql_object, field_name, value)
        if not sql_object.id:
            sql_object.save(sync_to_couch=False)
        sql_object.set_fields([
            SQLField(
                slug=field.slug,
                is_required=field.is_required,
                label=field.label,
                choices=field.choices,
                regex=field.regex,
                regex_msg=field.regex_msg,
            ) for field in self.fields
        ])
        sql_object.save(sync_to_couch=False)

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLCustomDataFieldsDefinition

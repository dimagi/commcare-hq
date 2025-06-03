import re
import uuid

from django.db import models, transaction
from django.utils.translation import gettext as _

from corehq.apps.data_cleaning.exceptions import UnsupportedActionException
from corehq.apps.data_cleaning.models.types import EditActionType
from corehq.apps.data_cleaning.utils.decorators import retry_on_integrity_error


class BulkEditChangeManager(models.Manager):
    use_for_related_fields = True

    def apply_inline_edit(self, record, prop_id, value):
        """
        Apply an inline edit to a record.
        :param record: BulkEditRecord
        :param prop_id: the id of the property to edit
        :param value: the new value for the property
        :return: BulkEditChange
        """
        change = self.create(
            session=record.session,
            prop_id=prop_id,
            action_type=EditActionType.REPLACE,
            replace_string=value,
        )
        change.records.add(record)
        return change

    @retry_on_integrity_error(max_retries=3, delay=0.1)
    @transaction.atomic
    def apply_reset(self, record, prop_id):
        """
        Apply a reset to a record.
        :param record: BulkEditRecord
        :param prop_id: the id of the property to edit
        :return: BulkEditChange
        """
        change = self.create(
            session=record.session,
            prop_id=prop_id,
            action_type=EditActionType.RESET,
        )
        change.records.add(record)
        return change


class BulkEditChange(models.Model):
    session = models.ForeignKey("data_cleaning.BulkEditSession", related_name="changes", on_delete=models.CASCADE)
    change_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    records = models.ManyToManyField("data_cleaning.BulkEditRecord", related_name="changes")
    prop_id = models.CharField(max_length=255)  # case property or form question_id
    action_type = models.CharField(
        max_length=12,
        choices=EditActionType.DB_CHOICES,
    )
    find_string = models.TextField(null=True, blank=True)
    replace_string = models.TextField(null=True, blank=True)
    use_regex = models.BooleanField(default=False)
    copy_from_prop_id = models.CharField(max_length=255)

    objects = BulkEditChangeManager()

    class Meta:
        ordering = ["created_on"]

    @property
    def action_title(self):
        """
        Returns a human-readable title of the action.
        """
        return dict(EditActionType.CHOICES).get(self.action_type, _("Unknown action"))

    @property
    def action_detail(self):
        """
        Returns a human-readable detail of the action.
        To be read as {{ action_title }} {{ action_detail }}
        """
        if self.action_type == EditActionType.REPLACE:
            return _('value with "{replace_string}".').format(
                replace_string=self.replace_string,
            )
        elif self.action_type == EditActionType.FIND_REPLACE:
            return _('"{find_string}" with "{replace_string}"{use_regex}.').format(
                find_string=self.find_string,
                replace_string=self.replace_string,
                use_regex=_(" (using regex)") if self.use_regex else "",
            )
        elif self.action_type == EditActionType.COPY_REPLACE:
            return _('from case property "{copy_from_prop_id}".').format(
                copy_from_prop_id=self.copy_from_prop_id,
            )
        return ""

    @property
    def num_records(self):
        return self.records.count()

    def edited_value(self, case, edited_properties=None):
        """
        Note: `BulkEditChange`s can be chained/layered. In order to properly chain
        changes, please call BulkEditRecord.get_edited_case_properties(case) to
        properly layer all changes in order.
        """
        edited_properties = edited_properties or {}
        old_value = edited_properties.get(self.prop_id, case.get_case_property(self.prop_id))

        simple_transformations = {
            EditActionType.REPLACE: lambda x: self.replace_string,
            EditActionType.MAKE_EMPTY: lambda x: "",
            EditActionType.MAKE_NULL: lambda x: None,
        }

        if self.action_type in simple_transformations:
            return simple_transformations[self.action_type](old_value)

        if self.action_type == EditActionType.COPY_REPLACE:
            return edited_properties.get(
                self.copy_from_prop_id, case.get_case_property(self.copy_from_prop_id)
            )

        if self.action_type == EditActionType.RESET:
            return case.get_case_property(self.prop_id)

        # all transformations past this point will throw an error if None is passed to it
        if old_value is None:
            return None
        return self._string_edited_value(old_value)

    def _string_edited_value(self, old_value):
        # ensure that the old_value is always a string
        old_value = str(old_value)

        string_regex_transformations = {
            EditActionType.FIND_REPLACE: lambda x: re.sub(
                re.compile(self.find_string), self.replace_string, x
            ),
        }
        if self.use_regex and self.action_type in string_regex_transformations:
            return string_regex_transformations[self.action_type](old_value)

        string_transformations = {
            EditActionType.FIND_REPLACE: lambda x: x.replace(self.find_string, self.replace_string),
            EditActionType.STRIP: str.strip,
            EditActionType.TITLE_CASE: str.title,
            EditActionType.UPPER_CASE: str.upper,
            EditActionType.LOWER_CASE: str.lower,
        }
        if self.action_type in string_transformations:
            return string_transformations[self.action_type](old_value)

        raise UnsupportedActionException(f"edited_value did not recognize action_type {self.action_type}")

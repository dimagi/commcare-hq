import re
import uuid

from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy, gettext as _

from corehq.apps.case_search.const import METADATA_IN_REPORTS
from corehq.apps.data_cleaning.exceptions import UnsupportedActionException


class BulkEditSessionType:
    CASE = 'case'
    FORM = 'form'
    CHOICES = (
        (CASE, "Case"),
        (FORM, "Form"),
    )


class BulkEditSession(models.Model):
    user = models.ForeignKey(User, related_name="bulk_edit_sessions", on_delete=models.CASCADE)
    domain = models.CharField(max_length=255, db_index=True)
    created_on = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    session_type = models.CharField(
        max_length=4,
        choices=BulkEditSessionType.CHOICES,
    )
    identifier = models.CharField(max_length=255, db_index=True)
    committed_on = models.DateTimeField(null=True, blank=True)
    task_id = models.UUIDField(null=True, blank=True, unique=True, db_index=True)
    result = models.JSONField(null=True, blank=True)
    completed_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_on"]

    @classmethod
    def get_active_case_session(cls, user, domain_name, case_type):
        return cls._get_active_session(user, domain_name, case_type, BulkEditSessionType.CASE)

    @classmethod
    def get_active_form_session(cls, user, domain_name, xmlns):
        return cls._get_active_session(user, domain_name, xmlns, BulkEditSessionType.FORM)

    @classmethod
    def _get_active_session(cls, user, domain_name, identifier, session_type):
        try:
            return cls.objects.get(
                user=user,
                domain=domain_name,
                identifier=identifier,
                session_type=session_type,
                committed_on=None,
                completed_on=None,
            )
        except cls.DoesNotExist:
            return None

    @classmethod
    def new_case_session(cls, user, domain_name, case_type):
        case_session = cls.objects.create(
            user=user,
            domain=domain_name,
            identifier=case_type,
            session_type=BulkEditSessionType.CASE,
        )
        BulkEditPinnedFilter.create_default_filters(case_session)
        BulkEditColumn.create_default_columns(case_session)
        return case_session

    @classmethod
    def restart_case_session(cls, user, domain_name, case_type):
        previous_session = cls.get_active_case_session(user, domain_name, case_type)
        previous_session.delete()
        new_session = cls.new_case_session(user, domain_name, case_type)
        return new_session

    @classmethod
    def new_form_session(cls, user, domain_name, xmlns):
        raise NotImplementedError("Form data cleaning sessions are not yet supported!")

    @classmethod
    def get_committed_sessions(cls, user, domain_name):
        return cls.objects.filter(user=user, domain=domain_name, committed_on__isnull=False)

    @property
    def status(self):
        if self.committed_on:
            if self.completed_on:
                return "complete"
            else:
                return "in progress"
        return "pending"


class DataType:
    TEXT = 'text'
    INTEGER = 'integer'
    PHONE_NUMBER = 'phone_number'
    DECIMAL = 'decimal'
    DATE = 'date'
    TIME = 'time'
    DATETIME = 'datetime'
    SINGLE_OPTION = 'single_option'
    MULTIPLE_OPTION = 'multiple_option'
    GPS = 'gps'
    BARCODE = 'barcode'
    PASSWORD = 'password'

    CHOICES = (
        (TEXT, gettext_lazy("Text")),
        (INTEGER, gettext_lazy("Integer")),
        (PHONE_NUMBER, gettext_lazy("Phone Number or Numeric ID")),
        (DECIMAL, gettext_lazy("Decimal")),
        (DATE, gettext_lazy("Date")),
        (TIME, gettext_lazy("Time")),
        (DATETIME, gettext_lazy("Date and Time")),
        (SINGLE_OPTION, gettext_lazy("Single Option")),
        (MULTIPLE_OPTION, gettext_lazy("Multiple Option")),
        (GPS, gettext_lazy("GPS")),
        (BARCODE, gettext_lazy("Barcode")),
        (PASSWORD, gettext_lazy("Password")),
    )


class FilterMatchType:
    EXACT = "exact"
    IS_NOT = "is_not"

    STARTS = "starts"
    ENDS = "ends"

    IS_EMPTY = "is_empty"  # empty string
    IS_NOT_EMPTY = "is_not_empty"

    IS_NULL = "is_null"  # un-set
    IS_NOT_NULL = "is_not_null"

    FUZZY = "fuzzy"  # will use fuzzy-match from CQL
    FUZZY_NOT = "not_fuzzy"  # will use not(fuzzy-match()) from CQL

    PHONETIC = "phonetic"  # will use phonetic-match from CQL
    PHONETIC_NOT = "not_phonetic"  # will use not(phonetic-match()) from CQL

    LESS_THAN = "lt"
    GREATER_THAN = "gt"

    IS_ANY = "is_any"  # we will use selected-any from CQL
    IS_NOT_ANY = "is_not_any"  # we will use not(selected-any()) from CQL

    IS_ALL = "is_all"  # we will use selected-all from CQL
    IS_NOT_ALL = "is_not_all"  # we will use not(selected-all()) from CQL

    ALL_CHOICES = (
        (EXACT, EXACT),
        (IS_NOT, IS_NOT),
        (STARTS, STARTS),
        (ENDS, ENDS),
        (IS_EMPTY, IS_EMPTY),
        (IS_NOT_EMPTY, IS_NOT_EMPTY),
        (IS_NULL, IS_NULL),
        (IS_NOT_NULL, IS_NOT_NULL),
        (FUZZY, FUZZY),
        (FUZZY_NOT, FUZZY_NOT),
        (PHONETIC, PHONETIC),
        (PHONETIC_NOT, PHONETIC_NOT),
        (LESS_THAN, LESS_THAN),
        (GREATER_THAN, GREATER_THAN),
        (IS_ANY, IS_ANY),
        (IS_NOT_ANY, IS_NOT_ANY),
        (IS_ALL, IS_ALL),
        (IS_NOT_ALL, IS_NOT_ALL),
    )

    TEXT_CHOICES = (
        (EXACT, gettext_lazy("is exactly")),
        (IS_NOT, gettext_lazy("is not")),
        (STARTS, gettext_lazy("starts with")),
        (ENDS, gettext_lazy("ends with")),
        (IS_EMPTY, gettext_lazy("is empty")),
        (IS_NOT_EMPTY, gettext_lazy("is not empty")),
        (IS_NULL, gettext_lazy("is NULL")),
        (IS_NOT_NULL, gettext_lazy("is not NULL")),
        (FUZZY, gettext_lazy("is like")),
        (FUZZY_NOT, gettext_lazy("is not like")),
        (PHONETIC, gettext_lazy("sounds like")),
        (PHONETIC_NOT, gettext_lazy("does not sound like")),
        (LESS_THAN, gettext_lazy("is before")),
        (GREATER_THAN, gettext_lazy("is after")),
    )

    MULTI_SELECT_CHOICES = (
        (IS_ANY, gettext_lazy("is any")),
        (IS_NOT_ANY, gettext_lazy("is not any")),
        (IS_ALL, gettext_lazy("is all")),
        (IS_NOT_ALL, gettext_lazy("is not all")),
    )

    NUMBER_CHOICES = (
        (EXACT, gettext_lazy("equals")),
        (IS_NOT, gettext_lazy("does not equal")),
        (LESS_THAN, gettext_lazy("less than")),
        (ENDS, gettext_lazy("less than or equal to")),
        (GREATER_THAN, gettext_lazy("greater than")),
        (STARTS, gettext_lazy("greater than or equal to")),
    )

    DATE_CHOICES = (
        (EXACT, gettext_lazy("on")),
        (LESS_THAN, gettext_lazy("before")),
        (GREATER_THAN, gettext_lazy("after")),
    )


class BulkEditColumnFilter(models.Model):
    session = models.ForeignKey(BulkEditSession, related_name="column_filters", on_delete=models.CASCADE)
    index = models.IntegerField(default=0)
    prop_id = models.CharField(max_length=255)  # case property or form question_id
    data_type = models.CharField(
        max_length=15,
        default=DataType.TEXT,
        choices=DataType.CHOICES,
    )
    match_type = models.CharField(
        max_length=12,
        default=FilterMatchType.EXACT,
        choices=FilterMatchType.ALL_CHOICES,
    )
    value = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["index"]


class PinnedFilterType:
    CASE_OWNERS = 'case_owners'
    CASE_STATUS = 'case_status'

    CHOICES = (
        (CASE_OWNERS, CASE_OWNERS),
        (CASE_STATUS, CASE_STATUS),
    )

    DEFAULT_FOR_CASE = (
        CASE_OWNERS, CASE_STATUS
    )


class BulkEditPinnedFilter(models.Model):
    session = models.ForeignKey(BulkEditSession, related_name="pinned_filters", on_delete=models.CASCADE)
    index = models.IntegerField(default=0)
    filter_type = models.CharField(
        max_length=11,
        choices=PinnedFilterType.CHOICES,
    )
    value = ArrayField(
        models.TextField(),
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["index"]

    @classmethod
    def create_default_filters(cls, session):
        default_types = {
            BulkEditSessionType.CASE: PinnedFilterType.DEFAULT_FOR_CASE,
        }.get(session.session_type)

        if not default_types:
            raise NotImplementedError(f"{session.session_type} default pinned filters not yet supported")

        for index, filter_type in enumerate(default_types):
            cls.objects.create(
                session=session,
                index=index,
                filter_type=filter_type,
            )


class BulkEditColumn(models.Model):
    session = models.ForeignKey(BulkEditSession, related_name="columns", on_delete=models.CASCADE)
    index = models.IntegerField(default=0)
    prop_id = models.CharField(max_length=255)  # case property or form question_id
    label = models.CharField(max_length=255)
    data_type = models.CharField(
        max_length=15,
        default=DataType.TEXT,
        choices=DataType.CHOICES,
    )
    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ["index"]

    @staticmethod
    def get_default_label(prop_id):
        known_labels = {
            'name': _("Name"),
            'owner_name': _('Owner'),
            'opened_on': _("Opened On"),
            'opened_by_username': _("Created By"),
            'modified_on': _("Last Modified On"),
            '@status': _("Status"),
        }
        return known_labels.get(prop_id, prop_id)

    @staticmethod
    def is_system_property(prop_id):
        return prop_id in set(METADATA_IN_REPORTS).difference({
            'name', 'case_name', 'external_id',
        })

    @classmethod
    def create_default_columns(cls, session):
        default_properties = {
            BulkEditSessionType.CASE: (
                'name', 'owner_name', 'opened_on', 'opened_by_username',
                'modified_on', '@status',
            ),
        }.get(session.session_type)

        if not default_properties:
            raise NotImplementedError(f"{session.session_type} default columns not yet supported")

        for index, prop_id in enumerate(default_properties):
            cls.objects.create(
                session=session,
                index=index,
                prop_id=prop_id,
                label=cls.get_default_label(prop_id),
                is_system=cls.is_system_property(prop_id),
            )


class BulkEditRecord(models.Model):
    session = models.ForeignKey(BulkEditSession, related_name="records", on_delete=models.CASCADE)
    doc_id = models.CharField(max_length=126, unique=True, db_index=True)  # case_id or form_id
    is_selected = models.BooleanField(default=True)
    calculated_change_id = models.UUIDField(null=True, blank=True)
    calculated_properties = models.JSONField(null=True, blank=True)

    @property
    def has_property_updates(self):
        return self.changes.count() > 0 and (
            self.calculated_change_id is None or self.changes.last().change_id != self.calculated_change_id
        )

    def get_edited_case_properties(self, case):
        """
        Returns a dictionary of properties that have been edited by related BulkEditChanges.
        :param case: CommCareCase
        """
        if case.case_id != self.doc_id:
            raise ValueError("case.case_id doesn't match record.doc_id")

        if not self.has_property_updates:
            return self.calculated_properties or {}

        properties = {}
        for change in self.changes.all():
            properties[change.prop_id] = change.edited_value(case, edited_properties=properties)
        self.calculated_properties = properties
        self.calculated_change_id = self.changes.last().change_id
        self.save()
        return properties


class EditActionType:
    REPLACE = 'replace'
    FIND_REPLACE = 'find_replace'
    STRIP = 'strip'
    COPY_REPLACE = 'copy_replace'
    TITLE_CASE = 'title_case'
    UPPER_CASE = 'upper_case'
    LOWER_CASE = 'lower_case'
    MAKE_EMPTY = 'make_empty'
    MAKE_NULL = 'make_null'
    RESET = 'reset'

    CHOICES = (
        (REPLACE, gettext_lazy("Replace")),
        (FIND_REPLACE, gettext_lazy("Find & Replace")),
        (COPY_REPLACE, gettext_lazy("Copy & Replace")),
        (STRIP, gettext_lazy("Strip Whitespaces")),
        (TITLE_CASE, gettext_lazy("Make Title Case")),
        (UPPER_CASE, gettext_lazy("Make Upper Case")),
        (LOWER_CASE, gettext_lazy("Make Lower Case")),
        (MAKE_EMPTY, gettext_lazy("Make Value Empty")),
        (MAKE_NULL, gettext_lazy("Make Value NULL")),
        (RESET, gettext_lazy("Undo All Edits")),
    )


class BulkEditChange(models.Model):
    session = models.ForeignKey(BulkEditSession, related_name="changes", on_delete=models.CASCADE)
    change_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    records = models.ManyToManyField(BulkEditRecord, related_name="changes")
    prop_id = models.CharField(max_length=255)  # case property or form question_id
    action_type = models.CharField(
        max_length=12,
        choices=EditActionType.CHOICES,
    )
    find_string = models.TextField(null=True, blank=True)
    replace_string = models.TextField(null=True, blank=True)
    use_regex = models.BooleanField(default=False)
    copy_from_prop_id = models.CharField(max_length=255)

    class Meta:
        ordering = ["created_on"]

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

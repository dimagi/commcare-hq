import uuid

from django.contrib.auth.models import User
from django.db import models, transaction

from corehq.apps.data_cleaning.models.types import (
    BulkEditSessionType,
)
from dimagi.utils.chunked import chunked

from corehq.apps.data_cleaning.utils.decorators import retry_on_integrity_error
from corehq.apps.es import CaseSearchES

BULK_OPERATION_CHUNK_SIZE = 1000
MAX_RECORDED_LIMIT = 100000
MAX_SESSION_CHANGES = 200
APPLY_CHANGES_WAIT_TIME = 15  # seconds


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
    def new_case_session(cls, user, domain_name, case_type, is_default=True):
        case_session = cls.objects.create(
            user=user,
            domain=domain_name,
            identifier=case_type,
            session_type=BulkEditSessionType.CASE,
        )
        if is_default:
            case_session.pinned_filters.create_session_defaults(case_session)
            case_session.columns.create_session_defaults(case_session)
        return case_session

    @classmethod
    @retry_on_integrity_error(max_retries=3, delay=0.1)
    def restart_case_session(cls, user, domain_name, case_type):
        with transaction.atomic():
            previous_session = cls.get_active_case_session(user, domain_name, case_type)
            if previous_session:
                previous_session.delete()
            new_session = cls.new_case_session(user, domain_name, case_type)
        return new_session

    @classmethod
    def new_form_session(cls, user, domain_name, xmlns):
        raise NotImplementedError("Form bulk edit sessions are not yet supported!")

    @classmethod
    def get_committed_sessions(cls, user, domain_name):
        return cls.objects.filter(user=user, domain=domain_name, committed_on__isnull=False)

    @classmethod
    def get_all_sessions(cls, user, domain_name):
        return cls.objects.filter(user=user, domain=domain_name).order_by('-created_on')

    def get_resumed_session(self):
        new_session = self.new_case_session(
            self.user,
            self.domain,
            self.identifier,
            is_default=False,
        )
        self.pinned_filters.copy_to_session(self, new_session)
        self.filters.copy_to_session(self, new_session)
        self.columns.copy_to_session(self, new_session)
        return new_session

    @property
    def is_read_only(self):
        return self.committed_on is not None

    @property
    def form_ids(self):
        if self.result is None or 'form_ids' not in self.result:
            return []
        return self.result['form_ids']

    @property
    def percent_complete(self):
        if self.result is None or 'percent' not in self.result:
            return None
        return round(self.result['percent'])

    @property
    def has_any_filtering(self):
        return self.has_pinned_values or self.has_filters

    def reset_filtering(self):
        self.reset_filters()
        self.reset_pinned_filters()

    @property
    def has_filters(self):
        return self.filters.count() > 0

    def reset_filters(self):
        self.filters.all().delete()

    @property
    def has_pinned_values(self):
        return any(self.pinned_filters.values_list('value', flat=True))

    def reset_pinned_filters(self):
        for pinned_filter in self.pinned_filters.all():
            pinned_filter.value = None
            pinned_filter.save()

    def add_filter(self, prop_id, data_type, match_type, value=None):
        """
        Add a filter to this session.

        :param prop_id: string - The property ID (e.g., case property)
        :param data_type: DataType - the data type of the property
        :param data_type: FilterMatchType - the type of match to perform
        :param value: string - The value to filter on
        :return: The created BulkEditFilter
        """
        return self.filters.create_for_session(self, prop_id, data_type, match_type, value)

    def add_column(self, prop_id, label, data_type=None):
        """
        Add a column to this session.

        :param prop_id: string - The property ID (e.g., case property)
        :param label: string - The column label to display
        :param data_type: DataType - Optional. Will be inferred for system props
        :return: The created BulkEditColumn
        """
        return self.columns.create_for_session(self, prop_id, label, data_type)

    @staticmethod
    def _update_order(related_manager, id_field, provided_ids):
        """
        Updates the ordering of related objects by setting their `index` field.

        :param related_manager: a Django RelatedManager (e.g., self.filters, self.columns)
        :param id_field: string name of the object's unique identifier (e.g., 'filter_id')
        :param provided_ids: list of UUIDs in desired order
        """
        if len(provided_ids) != related_manager.count():
            raise ValueError(
                "The lengths of provided_ids and ALL existing objects do not match. "
                "Please provide a list of ALL existing object ids in the desired order."
            )

        # NOTE: We cast the id_field to a string in the instance map to avoid UUID comparison
        # as the forms will be sending the ids as strings, while the remove_method sends it
        # as UUID objects.
        instance_map = {str(getattr(obj, id_field)): obj for obj in related_manager.all()}
        for index, object_id in enumerate(provided_ids):
            try:
                # We need to cast the object_id to a string to match the instance_map keys
                # in case the provided_ids are UUIDs.
                instance = instance_map[str(object_id)]
            except KeyError:
                raise ValueError(f"Object with {id_field} {object_id} not found.")
            instance.index = index

        related_manager.bulk_update(instance_map.values(), ['index'])

    def update_filter_order(self, filter_ids):
        """
        This updates the order of filters for this session
        :param filter_ids: list of uuids matching filter_id field of BulkEditFilters
        """
        self._update_order(self.filters, 'filter_id', filter_ids)

    def update_column_order(self, column_ids):
        """
        This updates the order of columns for this session
        :param column_ids: list of uuids matching column_id field of BulkEditColumns
        """
        self._update_order(self.columns, 'column_id', column_ids)

    def _delete_and_update_order(self, related_manager, id_field, provided_id):
        """
        Deletes a related object by its unique identifier and reindexes the remaining
        related objects to maintain sequential ordering.

        This is typically used for managing indexed relationships (like filters or columns)
        that use an 'index' field to determine order.

        :param related_manager: A Django RelatedManager (e.g., self.filters, self.columns)
        :param id_field: The name of the unique identifier field (e.g., 'filter_id')
        :param provided_id: The ID of the object to be removed
        """
        related_manager.get(**{id_field: provided_id}).delete()
        remaining_ids = related_manager.values_list(id_field, flat=True)
        self._update_order(related_manager, id_field, remaining_ids)

    @retry_on_integrity_error(max_retries=3, delay=0.1)
    def remove_filter(self, filter_id):
        """
        Remove a BulkEditFilter from this session by its filter_id,
        and update the remaining filters to maintain correct index order.

        :param filter_id: UUID of the BulkEditFilter to remove
        """
        with transaction.atomic():
            self._delete_and_update_order(self.filters, 'filter_id', filter_id)

    @retry_on_integrity_error(max_retries=3, delay=0.1)
    def remove_column(self, column_id):
        """
        Remove a BulkEditColumn from this session by its column_id,
        and update the remaining columns to maintain correct index order.

        :param column_id: UUID of the BulkEditColumn to remove
        """
        with transaction.atomic():
            self._delete_and_update_order(self.columns, 'column_id', column_id)

    def get_queryset(self):
        query = CaseSearchES().domain(self.domain).case_type(self.identifier)
        query = self.filters.apply_to_query(self, query)
        query = self.pinned_filters.apply_to_query(self, query)
        return query

    def get_document_from_queryset(self, doc_id):
        """
        Get the CaseES doc from the queryset for this session.
        # todo update for FormES later

        :param doc_id: the id of the document (case / form)
        :return: the raw document from elasticsearch
        """
        return self.get_queryset().case_ids([doc_id]).run().hits[0]

    def get_num_selected_records(self):
        return self.records.filter(is_selected=True).count()

    def get_num_selected_records_in_queryset(self):
        case_ids = self.records.filter(is_selected=True).values_list(
            "doc_id", flat=True
        )

        from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTableData

        num_selected_records = 0
        for doc_ids in chunked(case_ids, BULK_OPERATION_CHUNK_SIZE, list):
            num_selected_records += ElasticTableData.get_total_records_in_query(
                self.get_queryset().case_ids(doc_ids)
            )

        return num_selected_records

    @retry_on_integrity_error(max_retries=3, delay=0.1)
    @transaction.atomic
    def apply_inline_edit(self, doc_id, prop_id, value):
        """
        Edit the value of a property for a document in this session.
        :param doc_id: the id of the document (case / form)
        :param prop_id: the property id to edit
        :param value: the new value to set
        """
        record = self.records.get_for_inline_editing(self, doc_id)
        self.changes.apply_inline_edit(record, prop_id, value)

    @retry_on_integrity_error(max_retries=3, delay=0.1)
    def _attach_change_to_records(self, change, doc_ids=None):
        """
        :param change: BulkEditChange
        :param doc_ids: None or list of doc ids
        """
        if doc_ids is None:
            selected_records = self.records.filter(is_selected=True)
        else:
            selected_records = self.records.filter(doc_id__in=doc_ids, is_selected=True)

        # M2M relationships don't support bulk_create, so we need to access the through model
        # to properly batch this action
        if selected_records:
            through = change.records.through
            rows = [
                through(bulkeditchange_id=change.pk, bulkeditrecord_id=record.pk)
                for record in selected_records
            ]
            through.objects.bulk_create(rows, ignore_conflicts=True)

    @transaction.atomic
    def apply_change_to_selected_records(self, change):
        """
        :param change: BulkEditChange - an UNSAVED instance
        :return: BulkEditChange - the saved instance
        """
        assert change.session == self
        change.save()  # save the change in the atomic block, rather than the form
        if self.has_any_filtering:
            self._apply_operation_on_queryset(
                lambda doc_ids: self._attach_change_to_records(change, doc_ids)
            )
        else:
            # If there are no filters, we can just apply the change to all selected records
            # this will be a faster operation for larger data sets
            self._attach_change_to_records(change)
        return change

    @property
    def num_changed_records(self):
        if not self.committed_on:
            raise RuntimeError(
                "Session not committed yet. Please commit the session first or use get_change_counts()"
            )
        return self.result['record_count'] if self.completed_on else self.records.count()

    def has_changes(self):
        return self.changes.exists()

    def are_bulk_edits_allowed(self):
        return self.changes.count() < MAX_SESSION_CHANGES

    def purge_records(self):
        """
        Delete all records that do not have changes or are not selected.
        """
        self.records.filter(is_selected=False, changes__isnull=True).delete()

    @retry_on_integrity_error(max_retries=3, delay=0.1)
    @transaction.atomic
    def undo_last_change(self):
        self.changes.last().delete()
        self.purge_records()

    @retry_on_integrity_error(max_retries=3, delay=0.1)
    @transaction.atomic
    def clear_all_changes(self):
        self.changes.all().delete()
        self.purge_records()

    def select_record(self, doc_id):
        return self.records.select(self, doc_id)

    def deselect_record(self, doc_id):
        return self.records.deselect(self, doc_id)

    def select_multiple_records(self, doc_ids):
        return self.records.select_multiple(self, doc_ids)

    def deselect_multiple_records(self, doc_ids):
        return self.records.deselect_multiple(self, doc_ids)

    def _apply_operation_on_queryset(self, operation):
        """
        Perform a bulk operation on the queryset for this session.
        :param operation: function to apply to each record (takes in doc ids as argument)
        """
        for doc_ids in chunked(
            self.get_queryset().scroll_ids(), BULK_OPERATION_CHUNK_SIZE, list
        ):
            operation(doc_ids)

    def select_all_records_in_queryset(self):
        """
        Select all records in the ESQuery queryset for this session.
        """
        self._apply_operation_on_queryset(lambda doc_ids: self.select_multiple_records(doc_ids))

    def deselect_all_records_in_queryset(self):
        """
        Select all records in the ESQuery queryset for this session.
        """
        self._apply_operation_on_queryset(lambda doc_ids: self.deselect_multiple_records(doc_ids))

    def _get_num_unrecorded(self):
        """
        Return the number of records in the current queryset that do not have an
        associated `BulkEditRecord` object.
        :return: int
        """
        num_unrecorded = 0
        for doc_ids in chunked(
            self.get_queryset().scroll_ids(), BULK_OPERATION_CHUNK_SIZE, list
        ):
            num_unrecorded += len(self.records.get_unrecorded_doc_ids(self, doc_ids))
        return num_unrecorded

    def can_select_all(self, table_num_records=None):
        """
        Check that, if all records are selected in the queryset,
        the number of `BulkEditRecords` records will not exceed `MAX_RECORDED_LIMIT`.

        Note: This operation might take a long time if the queryset is large.

        :param table_num_records: int
            The value from `table.paginator.count` in a `DataCleaningTableView`.
            Specifying this can help avoid a potentially expensive query.

        :return: bool - True if select_all_records_in_queryset() can be called without exceeding the limit
        """
        if table_num_records and table_num_records > MAX_RECORDED_LIMIT:
            return False

        num_records = self.records.count()
        if table_num_records and table_num_records + num_records <= MAX_RECORDED_LIMIT:
            return True
        # the most potentially expensive query is below:
        return num_records + self._get_num_unrecorded() <= MAX_RECORDED_LIMIT

    def update_result(self, record_count, form_id=None, error=None):
        result = self.result or {}

        if 'form_ids' not in result:
            result['form_ids'] = []
        if 'record_count' not in result:
            result['record_count'] = 0
        if 'percent' not in result:
            result['percent'] = 0
        if 'errors' not in result:
            result['errors'] = []

        if form_id:
            result['form_ids'].append(form_id)
        if error:
            result['errors'].append(error)
        result['record_count'] += record_count
        if self.records.count() == 0:
            result['percent'] = 100
        else:
            result['percent'] = result['record_count'] * 100 / self.records.count()

        self.result = result
        self.save(update_fields=['result'])

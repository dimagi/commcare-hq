from django.db import models, transaction

from corehq.apps.data_cleaning.models.types import EditActionType
from corehq.apps.data_cleaning.utils.decorators import retry_on_integrity_error


class BulkEditRecordManager(models.Manager):
    use_for_related_fields = True

    def get_for_inline_editing(self, session, doc_id):
        return self.get_or_create(
            session=session,
            doc_id=doc_id,
            defaults={'is_selected': False}
        )[0]

    def select(self, session, doc_id):
        record, _ = self.get_or_create(
            session=session,
            doc_id=doc_id,
            defaults={'is_selected': True}
        )
        if not record.is_selected:
            record.is_selected = True
            record.save()
        return record

    @retry_on_integrity_error(max_retries=3, delay=0.1)
    @transaction.atomic
    def deselect(self, session, doc_id):
        try:
            record = session.records.get(doc_id=doc_id)
        except self.model.DoesNotExist:
            return None

        if record.changes.count() > 0:
            record.is_selected = False
            record.save()
        else:
            record.delete()
            record = None

        return record

    @retry_on_integrity_error(max_retries=3, delay=0.1)
    @transaction.atomic
    def select_multiple(self, session, doc_ids):
        session.records.filter(
            doc_id__in=doc_ids,
            is_selected=False,
        ).update(is_selected=True)

        existing_ids = session.records.filter(
            session=session,
            doc_id__in=doc_ids,
        ).values_list("doc_id", flat=True)

        missing_ids = list(set(doc_ids) - set(existing_ids))
        new_records = [
            self.model(session=session, doc_id=doc_id, is_selected=True)
            for doc_id in missing_ids
        ]
        # using ignore_conflicts avoids IntegrityErrors if another
        # process inserts them concurrently:
        self.bulk_create(new_records, ignore_conflicts=True)

        # re-update any records that might still not be marked if there
        # were any conflicts above...
        session.records.filter(
            doc_id__in=doc_ids,
            is_selected=False,
        ).update(is_selected=True)

    @retry_on_integrity_error(max_retries=3, delay=0.1)
    @transaction.atomic
    def deselect_multiple(self, session, doc_ids):
        # update is_selected to False for all selected records that have changes
        session.records.filter(
            doc_id__in=doc_ids,
            is_selected=True,
            changes__isnull=False,
        ).update(is_selected=False)

        # delete all records that have no changes
        session.records.filter(
            doc_id__in=doc_ids,
            changes__isnull=True,
        ).delete()

    def get_unrecorded_doc_ids(self, session, doc_ids):
        recorded_doc_ids = session.records.filter(
            doc_id__in=doc_ids,
        ).values_list("doc_id", flat=True)
        return list(set(doc_ids) - set(recorded_doc_ids))


class BulkEditRecord(models.Model):
    session = models.ForeignKey("data_cleaning.BulkEditSession", related_name="records", on_delete=models.CASCADE)
    doc_id = models.CharField(max_length=126, db_index=True)  # case_id or form_id
    is_selected = models.BooleanField(default=True)
    calculated_change_id = models.UUIDField(null=True, blank=True)
    calculated_properties = models.JSONField(null=True, blank=True)

    objects = BulkEditRecordManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "doc_id"],
                name="unique_record_per_session",
            ),
        ]

    @property
    def has_property_updates(self):
        return self.changes.count() > 0 and (
            self.calculated_change_id is None or self.changes.last().change_id != self.calculated_change_id
        )

    @property
    def should_reset_changes(self):
        return self.changes.count() == 0 and self.calculated_change_id is not None

    def reset_changes(self, prop_id):
        self.changes.apply_reset(self, prop_id)

    def get_edited_case_properties(self, case):
        """
        Returns a dictionary of properties that have been edited by related BulkEditChanges.
        :param case: CommCareCase
        """
        if case.case_id != self.doc_id:
            raise ValueError("case.case_id doesn't match record.doc_id")

        if self.should_reset_changes:
            self.calculated_properties = None
            self.calculated_change_id = None
            self.save()
            return {}

        if not self.has_property_updates:
            return self.calculated_properties or {}

        properties = {}
        for change in self.changes.all():
            if change.action_type == EditActionType.RESET:
                if change.prop_id in properties:
                    del properties[change.prop_id]
            else:
                properties[change.prop_id] = change.edited_value(
                    case, edited_properties=properties
                )
        self.calculated_properties = properties
        self.calculated_change_id = self.changes.last().change_id
        self.save()
        return properties

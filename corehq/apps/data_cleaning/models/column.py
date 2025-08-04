import uuid

from django.db import models

from corehq.apps.case_search.const import METADATA_IN_REPORTS
from corehq.apps.data_cleaning.models.types import (
    BulkEditSessionType,
    DataType,
)


class BulkEditColumnManager(models.Manager):
    use_for_related_fields = True
    _DEFAULT_PROPERTIES_BY_SESSION_TYPE = {
        BulkEditSessionType.CASE: (
            'name',
            'owner_name',
            'date_opened',
            'opened_by_username',
            'last_modified',
            '@status',
        ),
    }

    def create_session_defaults(self, session):
        default_properties = self._DEFAULT_PROPERTIES_BY_SESSION_TYPE.get(session.session_type)
        if not default_properties:
            raise NotImplementedError(f'{session.session_type} default columns not yet supported')

        from corehq.apps.data_cleaning.utils.cases import (
            get_system_property_data_type,
            get_system_property_label,
        )

        for index, prop_id in enumerate(default_properties):
            self.create(
                session=session,
                index=index,
                prop_id=prop_id,
                label=get_system_property_label(prop_id),
                data_type=get_system_property_data_type(prop_id),
                is_system=self.model.is_system_property(prop_id),
            )

    def copy_to_session(self, source_session, dest_session):
        for column in self.filter(session=source_session):
            self.model.objects.create(
                session=dest_session,
                index=column.index,
                prop_id=column.prop_id,
                label=column.label,
                data_type=column.data_type,
                is_system=column.is_system,
            )

    def create_for_session(self, session, prop_id, label, data_type=None):
        is_system_property = self.model.is_system_property(prop_id)
        from corehq.apps.data_cleaning.utils.cases import get_system_property_data_type

        data_type = get_system_property_data_type(prop_id) if is_system_property else data_type
        return self.create(
            session=session,
            index=session.columns.count(),
            prop_id=prop_id,
            label=label,
            data_type=data_type or DataType.TEXT,
            is_system=is_system_property,
        )


class BulkEditColumn(models.Model):
    session = models.ForeignKey('data_cleaning.BulkEditSession', related_name='columns', on_delete=models.CASCADE)
    column_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    index = models.IntegerField(default=0)
    prop_id = models.CharField(max_length=255)  # case property or form question_id
    label = models.CharField(max_length=255)
    data_type = models.CharField(
        max_length=15,
        default=DataType.TEXT,
        choices=DataType.CHOICES,
    )
    is_system = models.BooleanField(default=False)

    objects = BulkEditColumnManager()

    class Meta:
        ordering = ['index']

    @staticmethod
    def is_system_property(prop_id):
        return prop_id in set(METADATA_IN_REPORTS).difference(
            {
                'name',
                'case_name',
                'external_id',
            }
        )

    @property
    def slug(self):
        """
        Returns a slugified version of the prop_id.
        """
        return self.prop_id.replace('@', '')

    @property
    def choice_label(self):
        """
        Returns the human-readable option visible in a select field.
        """
        return self.label if self.label == self.prop_id else f'{self.label} ({self.prop_id})'

from dateutil import parser as dateutil_parser

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import (
    PopulateSQLCommand,
)
from corehq.motech.models import ConnectionSettings


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(cls):
        return 'DataSetMap'

    @classmethod
    def sql_class(cls):
        from corehq.motech.dhis2.models import SQLDataSetMap
        return SQLDataSetMap

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            domain=doc['domain'],
            couch_id=doc['_id'],
            defaults={
                'connection_settings': get_connection_settings(
                    doc['domain'], doc.get('connection_settings_id'),
                ),
                'ucr_id': doc['ucr_id'],
                'description': doc['description'],
                'frequency': doc['frequency'],
                'day_to_send': doc['day_to_send'],
                'data_set_id': doc.get('data_set_id'),
                'org_unit_id': doc.get('org_unit_id'),
                'org_unit_column': doc.get('org_unit_column'),
                'period': doc.get('period'),
                'period_column': doc.get('period_column'),
                'attribute_option_combo_id': doc.get('attribute_option_combo_id'),
                'complete_date': as_date_or_none(doc['complete_date'])
            }
        )
        if created:
            for datavalue_map in doc['datavalue_maps']:
                model.datavalue_maps.create(
                    column=datavalue_map['column'],
                    data_element_id=datavalue_map['data_element_id'],
                    category_option_combo_id=datavalue_map['category_option_combo_id'],
                    comment=datavalue_map.get('comment'),
                )
        return (model, created)

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        diffs = []
        for attr in [
            'domain',
            'ucr_id',
            'description',
            'frequency',
            'day_to_send',
            'data_set_id',
            'org_unit_id',
            'org_unit_column',
            'period',
            'period_column',
            'attribute_option_combo_id',
        ]:
            diffs.append(cls.diff_attr(attr, couch, sql))
        diffs.append(cls.diff_attr('complete_date', couch, sql,
                                   wrap=as_date_or_none))
        diffs = [d for d in diffs if d]
        return "\n".join(diffs) if diffs else None


def get_connection_settings(domain, pk):
    if not pk:
        return None
    try:
        return ConnectionSettings.objects.get(domain=domain, pk=pk)
    except ConnectionSettings.DoesNotExist:
        return None


def as_date_or_none(date_str):
    """
    Casts a date string as a datetime.date, or None if it is blank.

    >>> as_date_or_none('2020-11-04')
    datetime.date(2020, 11, 4)
    >>> as_date_or_none('')
    None
    >>> as_date_or_none(None)
    None

    """
    if not date_str:
        return None
    return dateutil_parser.parse(date_str).date()

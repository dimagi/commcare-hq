"""
This files defines ETL objects that all have a common "load" function.
Each object is meant for transferring one type of data to another type.
"""

import os

from django.conf import settings
from django.db import connections
from django.template import engines

from corehq.sql_db.routers import db_for_read_write
from corehq.warehouse.loaders import get_loader_by_slug
from corehq.warehouse.utils import django_batch_records


class BaseETLMixin(object):

    def load(self, batch):
        raise NotImplementedError


class CustomSQLETLMixin(BaseETLMixin):
    """
    Mixin for transferring data from a SQL store to another SQL store using
    a custom SQL script.
    """
    def additional_sql_context(self):
        """
        Override this method to provide additional context
        vars to the SQL script
        """
        return {}

    def load(self, batch):
        from corehq.warehouse.loaders.base import BaseLoader
        """
        Bulk loads records for a dim or fact table from
        their corresponding dependencies
        """

        assert isinstance(self, BaseLoader)
        database = db_for_read_write(self.model_cls)
        with connections[database].cursor() as cursor:
            cursor.execute(self._sql_query_template(self.slug, batch))

    def _table_context(self, batch):
        """
        Get a dict of slugs to table name mapping
        :returns: Dict of slug to table_name
        {
            <slug>: <table_name>,
            ...
        }
        """

        context = slug_to_table_map(self.dependant_slugs() + [self.slug])
        context['start_datetime'] = batch.start_datetime.isoformat()
        context['end_datetime'] = batch.end_datetime.isoformat()
        context['batch_id'] = batch.id
        context.update(self.additional_sql_context())
        return context

    def _sql_query_template(self, template_name, batch):
        path = os.path.join(
            settings.BASE_DIR,
            'corehq',
            'warehouse',
            'transforms',
            'sql',
            '{}.sql'.format(template_name),
        )
        if not os.path.exists(path):
            raise NotImplementedError(
                'You must define {} in order to load data'.format(path)
            )

        return _render_template(path, self._table_context(batch))


class HQToWarehouseETLMixin(BaseETLMixin):
    """
    Mixin for transferring docs from Couch to a Django model.
    """

    def field_mapping(self):
        # Map source model fields to staging table fields
        # ( <source field>, <staging field> )
        raise NotImplementedError

    def validate(self):
        super(HQToWarehouseETLMixin, self).validate()
        model_fields = {field.name for field in self.model_cls._meta.fields}
        mapping_fields = {field for _, field in self.field_mapping()}
        missing = mapping_fields - model_fields
        if missing:
            raise Exception('Mapping fields refer to missing model fields', missing)

    def record_iter(self, start_datetime, end_datetime):
        raise NotImplementedError

    def load(self, batch):
        from corehq.warehouse.loaders.base import BaseLoader

        assert isinstance(self, BaseLoader)
        record_iter = self.record_iter(batch.start_datetime, batch.end_datetime)

        django_batch_records(self.model_cls, record_iter, self.field_mapping(), batch.id)


def _render_template(path, context):
    with open(path, 'rb') as f:
        template_string = f.read()

    template = engines['django'].from_string(template_string)
    return template.render(context)


def slug_to_table_map(slugs):
    mapping = {}
    for slug in slugs:
        loader_cls = get_loader_by_slug(slug)
        mapping[slug] = loader_cls().target_table()
    return mapping

'''
This files defines ETL objects that all have a common "load" function.
Each object is meant for transferring one type of data to another type.
'''

import os

from django.conf import settings
from django.db import connections
from django.template import engines

from corehq.sql_db.routers import db_for_read_write
from corehq.warehouse.utils import django_batch_records


class BaseETLMixin(object):

    @classmethod
    def load(cls, batch):
        raise NotImplementedError


class CustomSQLETLMixin(BaseETLMixin):
    '''
    Mixin for transferring data from a SQL store to another SQL store using
    a custom SQL script.
    '''
    @classmethod
    def additional_sql_context(cls):
        '''
        Override this method to provide additional context
        vars to the SQL script
        '''
        return {}

    @classmethod
    def load(cls, batch):
        from corehq.warehouse.loaders.base import BaseLoader
        '''
        Bulk loads records for a dim or fact table from
        their corresponding dependencies
        '''

        assert issubclass(cls, BaseLoader)
        database = db_for_read_write(cls.model_cls)
        with connections[database].cursor() as cursor:
            cursor.execute(cls._sql_query_template(cls.slug, batch))

    @classmethod
    def _table_context(cls, batch):
        '''
        Get a dict of slugs to table name mapping
        :returns: Dict of slug to table_name
        {
            <slug>: <table_name>,
            ...
        }
        '''
        from corehq.warehouse.loaders import get_loader_by_slug

        context = {cls.slug: cls.target_table()}
        for dep in cls.dependencies():
            loader_cls = get_loader_by_slug(dep)
            context[dep] = loader_cls.target_table()
        context['start_datetime'] = batch.start_datetime.isoformat()
        context['end_datetime'] = batch.end_datetime.isoformat()
        context['batch_id'] = batch.id
        context.update(cls.additional_sql_context())
        return context

    @classmethod
    def _sql_query_template(cls, template_name, batch):
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

        return _render_template(path, cls._table_context(batch))


class HQToWarehouseETLMixin(BaseETLMixin):
    '''
    Mixin for transferring docs from Couch to a Django model.
    '''

    @classmethod
    def field_mapping(cls):
        # Map source model fields to staging table fields
        # ( <source field>, <staging field> )
        raise NotImplementedError

    def validate(self):
        super(HQToWarehouseETLMixin, self).validate()
        model_fields = {field.name for field in self.model_cls._meta.fields}
        mapping_fields = {field for _, field in self.field_mapping()}
        missing = mapping_fields - model_fields
        if missing:
            raise Exception('Mapping fields not present on model', missing)

    @classmethod
    def record_iter(cls, start_datetime, end_datetime):
        raise NotImplementedError

    @classmethod
    def load(cls, batch):
        from corehq.warehouse.loaders.base import BaseLoader

        assert issubclass(cls, BaseLoader)
        record_iter = cls.record_iter(batch.start_datetime, batch.end_datetime)

        django_batch_records(cls.model_cls, record_iter, cls.field_mapping(), batch.id)


def _render_template(path, context):
    with open(path, 'rb') as f:
        template_string = f.read()

    template = engines['django'].from_string(template_string)
    return template.render(context)

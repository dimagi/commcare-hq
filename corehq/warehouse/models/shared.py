import os

from django.db import connections
from django.conf import settings
from django.template import Context, engines

from corehq.sql_db.routers import db_for_read_write

from corehq.warehouse.transforms import get_transform
from corehq.warehouse.const import (
    DJANGO_MAX_BATCH_SIZE,
)


class WarehouseTableMixin(object):

    @classmethod
    def sql_query_template_name(cls):
        return None

    @classmethod
    def dependencies(cls):
        raise NotImplementedError

    @classmethod
    def load(cls):
        '''
        Bulk loads records for a dim or fact table from
        their corresponding dependencies
        '''
        for record in cls.record_iter():
            print record

    @classmethod
    def _table_context(cls):
        '''
        Get a dict of slugs to table name mapping
        :returns: Dict of slug to table_name
        {
            <slug>: <table_name>,
            ...
        }
        '''
        from corehq.warehouse.models import get_cls_by_slug

        context = {cls.slug: cls._meta.db_table}
        for dep in cls.dependencies():
            dep_cls = get_cls_by_slug(dep)
            context[dep] = dep_cls._meta.db_table
        return context

    @classmethod
    def sql_query_template(cls, template_name):
        path = os.path.join(
            settings.BASE_DIR,
            'corehq',
            'warehouse',
            'transforms',
            'sql',
            '{}.sql'.format(template_name),
        )

        return _render_template(path, cls._table_context())

    @classmethod
    def record_iter(cls):
        '''
        Returns an iterator over all records to be updated in
        the table.
        '''
        database = db_for_read_write(cls)
        with connections[database].cursor() as cursor:
            cursor.execute(cls.sql_query_template(cls.slug))
            columns = [col[0] for col in cursor.description]
            for row in cursor:
                row_dict = dict(zip(columns, row))
                transformed = get_transform(cls.slug)(row_dict)
                yield transformed


def _render_template(path, context):
    with open(path) as f:
        template_string = f.read()

    template = engines['django'].from_string(template_string)
    return template.render(Context(context))

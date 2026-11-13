from django.db import migrations
from django.db.migrations.operations.models import ModelOperation

from architect.commands import partition


def get_sql():
    next_month = '2021-09-01 00:00:00 Z'  # TODO: Calculate this
    return f"""
        CREATE TABLE motech_requestlog (
            id integer NOT NULL,
            domain character varying(126) NOT NULL,
            "timestamp" timestamp with time zone NOT NULL,
            request_method character varying(12) NOT NULL,
            request_url character varying(255) NOT NULL,
            request_headers text NOT NULL,
            request_params text NOT NULL,
            request_body text,
            request_error text,
            response_status integer,
            response_body text,
            log_level integer,
            payload_id character varying(126),
            response_headers text
        );

        CREATE SEQUENCE motech_requestlog_id_seq
            START WITH 1
            INCREMENT BY 1
            NO MINVALUE
            NO MAXVALUE
            CACHE 1;

        ALTER SEQUENCE motech_requestlog_id_seq
            OWNED BY motech_requestlog.id;

        ALTER TABLE dhis2_jsonapilog
            ADD CONSTRAINT before_next_month
            CHECK ("timestamp" < TIMESTAMP '{next_month}');

        ALTER TABLE dhis2_jsonapilog
            INHERIT motech_requestlog;
    """


reverse_sql = """
    ALTER TABLE dhis2_jsonapilog
        NO INHERIT motech_requestlog;

    ALTER TABLE dhis2_jsonapilog
        DROP CONSTRAINT before_next_month;

    DROP SEQUENCE motech_requestlog_id_seq;

    DROP TABLE motech_requestlog;

"""


class PointModelAtTable(ModelOperation):
    """
    Point a model to a different table.

    The new table must already be set up as an exact replica of the
    current table. This class is therefore a state operation, and
    intentionally does not implement ``database_forwards()`` and
    ``database_backwards()``.
    """

    def __init__(self, name, table):
        self.table = table
        super().__init__(name)

    def deconstruct(self):
        kwargs = {
            'name': self.name,
            'table': self.table,
        }
        return self.__class__.__qualname__, [], kwargs

    def state_forwards(self, app_label, state):
        state.models[app_label, self.name_lower].options["db_table"] = self.table
        state.reload_model(app_label, self.name_lower, delay=True)

    def describe(self):
        return f"Point model {self.name} at table {self.table}"


def add_partitions(apps, schema_editor):
    partition.run({'module': 'corehq.motech.models'})


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0008_requestlog_response_headers'),
    ]

    operations = [
        migrations.RunSQL(
            get_sql(),
            reverse_sql=reverse_sql,
            state_operations=[PointModelAtTable(
                name='requestlog',
                table='motech_requestlog',
            )],
        ),
        migrations.RunPython(add_partitions),
    ]

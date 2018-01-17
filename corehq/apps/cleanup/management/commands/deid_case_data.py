from __future__ import absolute_import
from __future__ import print_function

from django.core.management.base import BaseCommand
from django.db import connections

from corehq.form_processor.utils.sql import fetchone_as_namedtuple
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.log import with_progress_bar

DEID_FIELDS = {
    'household': [
        "name",
        "hh_gps_location",
    ],
    'person': [
        "phone_number",
        "contact_phone_number",
        "name",
        "date_primary_admit",
        "aadhar_number",
        "mcts_id",
        "dob",
        "raw_aadhar_string",
        "mcp_id",
        "rch_id",
        "date_death",
        "date_last_private_admit",
        "bank_account_number",
        "referral_reached_date",
        "time_birth",
    ],
    'child_health': ["name"],
    'measurement': ["name"],
    'tasks': ["name"],
    'commcare-user': [
        "phone_number",
        "helpdesk_phone_number",
        "dob_aww",
        "contact_phone_number",
        "name",
        "ls_name",
        "ls_phone_number",
        "dimagi_username",
        "email",
    ],
    'ccs_record': [
        "phone_number",
        "contact_phone_number",
        "name",
        "date_primary_admit",
        "aadhar_number",
        "mcts_id",
        "dob",
        "raw_aadhar_string",
        "mcp_id",
        "rch_id",
        "date_death",
        "date_last_private_admit",
        "bank_account_number",
        "referral_reached_date",
        "time_birth",
    ],
}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('database')

    def handle(self, domain, database, **options):
        assert database in get_db_aliases_for_partitioned_query()
        _create_function(database)

        with connections[database].cursor() as cursor:
            cursor.execute(
                "select min(id) as min_id, max(id) as max_id from form_processor_commcarecasesql"
            )
            result = fetchone_as_namedtuple(cursor)
            global_min_id, global_max_id = result.min_id, result.max_id

        print("Data range: %s to %s" % (global_min_id, global_max_id))
        rows_to_update = 10000
        batches = [
            (min, min + rows_to_update)
            for min in range(global_min_id, global_max_id, rows_to_update)
        ]
        for case_type, fields in DEID_FIELDS.items():
            print("Updating '%s' data" % case_type)
            keys = '{"%s"}' % '", "'.join(fields)  # '{"f1","f2",...}'
            values = '{%s}' % ','.join(['""'] * len(fields))  # '{"","",...}'
            for batch in with_progress_bar(batches, oneline=True):
                min_id, max_id = batch
                with connections[database].cursor() as cursor:
                    cursor.execute("""
                        UPDATE form_processor_commcarecasesql
                        SET case_json = json_object_set_keys(case_json::json, %s::TEXT[], %s::TEXT[])
                        WHERE domain = %s and type = %s AND id > %s AND id <= %s;
                    """, [keys, values, domain, case_type, min_id, max_id])

                min_id += rows_to_update
                max_id += rows_to_update


def _create_function(db_name):
    # https://stackoverflow.com/questions/18209625/how-do-i-modify-fields-inside-the-new-postgresql-json-datatype/23500670
    with connections[db_name].cursor() as cursor:
        cursor.execute("""
        CREATE OR REPLACE FUNCTION "json_object_set_keys"(
          "json"          json,
          "keys_to_set"   TEXT[],
          "values_to_set" anyarray
        )
          RETURNS json
          LANGUAGE sql
          IMMUTABLE
          STRICT
        AS $function$
        SELECT concat('{', string_agg(to_json("key") || ':' || "value", ','), '}')::json
          FROM (SELECT *
                  FROM json_each("json")
                 WHERE "key" <> ALL ("keys_to_set")
                 UNION ALL
                SELECT DISTINCT ON ("keys_to_set"["index"])
                       "keys_to_set"["index"],
                       CASE
                         WHEN "values_to_set"["index"] IS NULL THEN 'null'::json
                         ELSE to_json("values_to_set"["index"])
                       END
                  FROM generate_subscripts("keys_to_set", 1) AS "keys"("index")
                  JOIN generate_subscripts("values_to_set", 1) AS "values"("index")
                 USING ("index")) AS "fields"
        $function$;
        """)

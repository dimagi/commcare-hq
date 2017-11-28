from __future__ import absolute_import
from datetime import datetime
from django.db import connections
from django.core.management.base import BaseCommand
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from six.moves import range


def foreign_key_exists(db_alias, table_name, foreign_column_key_name):
    cursor = connections[db_alias].cursor()
    cursor.execute(
        "SELECT 1 "
        "FROM information_schema.table_constraints A "
        "JOIN information_schema.key_column_usage B "
        "ON A.constraint_name = B.constraint_name "
        "AND A.table_name = B.table_name "
        "WHERE A.table_name = %s "
        "AND B.column_name = %s"
        "AND A.constraint_type = 'FOREIGN KEY' ",
        [table_name, foreign_column_key_name]
    )
    return cursor.fetchone() is not None


def add_locations_sqllocation_parent_fk(db_alias):
    cursor = connections[db_alias].cursor()
    cursor.execute(
        "ALTER TABLE locations_sqllocation "
        "ADD CONSTRAINT locations_sqlloc_parent_id_2ffc03fb_fk_locations_sqllocation_id "
        "FOREIGN KEY (parent_id) REFERENCES locations_sqllocation(id) DEFERRABLE INITIALLY DEFERRED"
    )


def add_form_processor_xformattachmentsql_form_id_fk(db_alias):
    cursor = connections[db_alias].cursor()
    cursor.execute(
        "ALTER TABLE form_processor_xformattachmentsql "
        "ADD CONSTRAINT for_form_id_d184240c_fk_form_processor_xforminstancesql_form_id "
        "FOREIGN KEY (form_id) REFERENCES form_processor_xforminstancesql(form_id) DEFERRABLE INITIALLY DEFERRED"
    )


def add_form_processor_commcarecaseindexsql_case_id_fk(db_alias):
    cursor = connections[db_alias].cursor()
    cursor.execute(
        "ALTER TABLE form_processor_commcarecaseindexsql "
        "ADD CONSTRAINT form_case_id_be4cb9e1_fk_form_processor_commcarecasesql_case_id "
        "FOREIGN KEY (case_id) REFERENCES form_processor_commcarecasesql(case_id) DEFERRABLE INITIALLY DEFERRED"
    )


def add_form_processor_casetransaction_case_id_fk(db_alias):
    cursor = connections[db_alias].cursor()
    cursor.execute(
        "ALTER TABLE form_processor_casetransaction "
        "ADD CONSTRAINT form_case_id_0328b100_fk_form_processor_commcarecasesql_case_id "
        "FOREIGN KEY (case_id) REFERENCES form_processor_commcarecasesql(case_id) DEFERRABLE INITIALLY DEFERRED"
    )


class Command(BaseCommand):
    help = ""

    log_file = None

    def log(self, text, indent=0):
        self.log_file.write(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S: "))
        for i in range(indent):
            self.log_file.write('    ')
        self.log_file.write(text)
        self.log_file.write('\n')

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-only',
            action='store_true',
            dest='check_only',
            default=False,
            help="Only check if the foreign keys exist but don't add anything",
        )

    def try_to_add_fk(self, function, db_alias):
        try:
            function(db_alias)
            self.log("foreign key added", 2)
        except Exception as e:
            self.log("error adding foreign key: %s" % e, 2)

    def handle_locations_sqllocation(self):
        self.log("handling locations_sqllocation", 2)
        if foreign_key_exists('default', 'locations_sqllocation', 'parent_id'):
            self.log("foreign key exists", 2)
        else:
            self.log("foreign key DOES NOT exist", 2)
            if not self.check_only:
                self.try_to_add_fk(add_locations_sqllocation_parent_fk, 'default')

    def handle_form_processor_xformattachmentsql(self, db_alias):
        self.log("handling form_processor_xformattachmentsql", 2)
        if foreign_key_exists(db_alias, 'form_processor_xformattachmentsql', 'form_id'):
            self.log("foreign key exists", 2)
        else:
            self.log("foreign key DOES NOT exist", 2)
            if not self.check_only:
                self.try_to_add_fk(add_form_processor_xformattachmentsql_form_id_fk, db_alias)

    def handle_form_processor_commcarecaseindexsql(self, db_alias):
        self.log("handling form_processor_commcarecaseindexsql", 2)
        if foreign_key_exists(db_alias, 'form_processor_commcarecaseindexsql', 'case_id'):
            self.log("foreign key exists", 2)
        else:
            self.log("foreign key DOES NOT exist", 2)
            if not self.check_only:
                self.try_to_add_fk(add_form_processor_commcarecaseindexsql_case_id_fk, db_alias)

    def handle_form_processor_casetransaction(self, db_alias):
        self.log("handling form_processor_casetransaction", 2)
        if foreign_key_exists(db_alias, 'form_processor_casetransaction', 'case_id'):
            self.log("foreign key exists", 2)
        else:
            self.log("foreign key DOES NOT exist", 2)
            if not self.check_only:
                self.try_to_add_fk(add_form_processor_casetransaction_case_id_fk, db_alias)

    def handle(self, check_only, **options):
        self.check_only = check_only
        with open('add_back_enikshay_foreign_keys.log', 'a') as f:
            self.log_file = f
            self.log("")
            self.log("running script to add back missing foreign keys")
            self.log("check_only is: %s" % check_only)

            self.log("handling db: default", 1)
            self.handle_locations_sqllocation()

            for db_alias in get_db_aliases_for_partitioned_query():
                self.log("handling db: %s" % db_alias, 1)
                self.handle_form_processor_xformattachmentsql(db_alias)
                self.handle_form_processor_commcarecaseindexsql(db_alias)
                self.handle_form_processor_casetransaction(db_alias)

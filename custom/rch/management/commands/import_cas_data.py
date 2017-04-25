# -*- coding: utf-8 -*-
from django.core.management import BaseCommand
from xlrd import open_workbook
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from django.db import connection

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('path_to_file')

    def handle(self, path_to_file, *args, **options):
        sheet = open_workbook(path_to_file).sheets()[0]
        record = {}
        for row in range(2, sheet.nrows):
            for i in range(sheet.ncols):
                record[sheet.cell_value(0, i)] = sheet.cell_value(row, i)
            sql = "INSERT INTO form_processor_commcarecasesql" \
                  "(case_id, name, domain, type, owner_id, " \
                  "location_id, opened_on, opened_by, " \
                  "modified_on, server_modified_on, " \
                  "modified_by, closed, " \
                  "closed_by, deleted, case_json)" \
                  "VALUES('%s', '%s', '%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s', '%s','%s')" % (
                record['caseid'], record['name'], 'icds-cas', 'person', record['owner_id'],
                record['owner_id'], record['opened_date'], record['opened_by_username'],
                record['last_modified_date'], record['last_modified_date'],
                record['last_modified_by_user_username'], record['closed'],
                record['closed_by_username'], 'FALSE', {})
            connection.cursor().execute(sql)
            new_record = CaseAccessorSQL.get_case(record['caseid'])
            new_record.case_json = record
            CaseAccessorSQL.save_case(new_record)

from __future__ import absolute_import
from custom.enikshay.private_sector_datamigration.management.commands.base_cleanup_csv import BaseCleanupCSVCommand


class Command(BaseCleanupCSVCommand):

    @staticmethod
    def clean_rows(header, body):

        def _clean_row(row):
            assert len(row) >= len(header)

            agencyId = row[4]
            if not agencyId.isdigit():
                row = row[0:3] + [','.join(row[3:5])] + row[5:]

            bankName = row[12]
            if bankName not in ['NULL', ''] and not bankName.isdigit():
                row = row[0:10] + [','.join(row[10:12])] + row[12:]

            while len(row) > len(header):
                row = row[0:46] + [','.join(row[46:48])] + row[48:]

            boolean_field_to_value = {
                '\x01': 'TRUE',
                '\\0': 'FALSE',
            }
            row[22] = boolean_field_to_value[row[22]]
            row[35] = boolean_field_to_value[row[35]]
            row[45] = boolean_field_to_value[row[45]]

            return row

        return [header] + [_clean_row(row) for row in body]

from __future__ import absolute_import
from custom.enikshay.nikshay_datamigration.management.commands.base_cleanup_command import BaseCleanupCommand


class Command(BaseCleanupCommand):

    @staticmethod
    def clean_rows(rows, exclude_ids):
        new_rows = []
        cur_row = ['']

        for i, row in enumerate(rows):
            if row:
                cur_row[-1] = cur_row[-1] + row[0]  # concatenate first element in row with last element in cur_row
                cur_row.extend(row[1:])  # append remaining elements in row to cur_row

                if len(cur_row) == len(rows[0]):
                    cur_row[0] = cur_row[0].strip()
                    new_rows.append(cur_row)
                    cur_row = ['']

        return new_rows

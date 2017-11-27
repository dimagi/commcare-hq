from __future__ import absolute_import
from builtins import range
from custom.enikshay.nikshay_datamigration.management.commands.base_cleanup_command import BaseCleanupCommand

# before any changes
MO_INDEX = 3
XrayEPTests_INDEX = 4
MORemark_INDEX = 5


class Command(BaseCleanupCommand):

    headers = [
        'PatientId',
        'Outcome',
        'OutcomeDate',
        'MO',
        'XrayEPTests',
        'MORemark',
        'HIVStatus',
        'HIVTestDate',
        'CPTDeliverDate',
        'ARTCentreDate',
        'InitiatedOnART',
        'InitiatedDate',
        'userName',
    ]

    @staticmethod
    def clean_rows(rows, exclude_ids):
        new_rows = []
        cur_row = ['']

        new_rows.append(Command.headers)

        for i, row in enumerate(rows):
            if row:
                cur_row[-1] = cur_row[-1] + row[0]  # concatenate first element in row with last element in cur_row
                if i == 0:
                    cur_row[0] = cur_row[0][3:]
                cur_row.extend(row[1:])  # append remaining elements in row to cur_row

                while len(cur_row) > len(rows[0]):  # assume first row in csv has right number of columns
                    null_index = next((i for i, val in enumerate(cur_row) if val == 'NULL'), None)
                    assert null_index is not None
                    cur_row[MO_INDEX] = ','.join(cur_row[MO_INDEX:null_index])
                    for _ in range(XrayEPTests_INDEX, null_index):
                        del cur_row[XrayEPTests_INDEX]

                    num_extra_columns = len(cur_row) - len(rows[0])
                    cur_row[MORemark_INDEX] = ','.join(
                        cur_row[MORemark_INDEX:MORemark_INDEX + 1 + num_extra_columns]
                    )
                    for _ in range(num_extra_columns):
                        del cur_row[MORemark_INDEX + 1]

                if len(cur_row) == len(rows[0]):
                    cur_row[0] = cur_row[0].strip()
                    new_rows.append(cur_row)
                    cur_row = ['']

        return new_rows

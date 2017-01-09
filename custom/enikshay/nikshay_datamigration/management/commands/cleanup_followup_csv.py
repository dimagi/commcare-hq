from custom.enikshay.nikshay_datamigration.management.commands.base_cleanup_command import BaseCleanupCommand


class Command(BaseCleanupCommand):

    headers = [
        'id',
    ] + [
        'PatientID',
        'IntervalId',
        'TestDate',
        'DMC',
        'LabNo',
        'SmearResult',
        'PatientWeight',
        'DmcStoCode',
        'DmcDtoCode',
        'DmcTbuCode',
        'RegBy',
        'regdate',
    ]

    @staticmethod
    def clean_rows(rows, exclude_ids):
        new_rows = [Command.headers]

        for i, row in enumerate(rows):
            new_row = [i + 1] + row  # add id
            if i == 0:
                new_row[1] = new_row[1][3:]
            new_row[1] = new_row[1].strip()

            # TODO - figure out what's wrong with these rows
            if len(new_row) > len(new_rows[0]) and i in [1464815, 1484488]:
                continue
            if any(id in new_row[1] for id in exclude_ids):
                continue
            new_rows.append(new_row)

        return new_rows

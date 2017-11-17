from __future__ import absolute_import
from custom.enikshay.nikshay_datamigration.management.commands.base_cleanup_command import BaseCleanupCommand


class Command(BaseCleanupCommand):

    @staticmethod
    def clean_rows(rows, exclude_ids):
        return [
            [cell.strip() for cell in row] for row in rows
            if row[3] not in ['NULL', '']  # TestDate
        ]

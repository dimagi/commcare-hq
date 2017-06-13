from custom.enikshay.private_sector_datamigration.management.commands.base_cleanup_csv import BaseCleanupCSVCommand


class Command(BaseCleanupCSVCommand):

    @staticmethod
    def clean_rows(header, body):

        def _clean_row(row):
            assert len(row) >= len(header)
            while len(row) > len(header):
                row = row[0:25] + [','.join(row[25:27])] + row[27:]
            return row

        return [header] + [_clean_row(row) for row in body]

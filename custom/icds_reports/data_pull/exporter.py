import zipfile

from django.utils.functional import cached_property

from corehq.util.context_managers import prevent_parallel_execution
from custom.icds.const import DATA_PULL_CACHE_KEY
from custom.icds_reports.const import CUSTOM_DATA_PULLS
from custom.icds_reports.data_pull.data_pulls import DirectDataPull


class DataExporter(object):
    def __init__(self, slug_or_file, db_alias, month, location_id):
        """
        run data export by either passing slug to a custom data pull
        or file name/path to a sql file which will be read as a single query
        """
        if month:
            # convert to string if date object received
            month = str(month)
        self.slug_or_file = slug_or_file
        self.month = month
        self.location_id = location_id
        data_pull_class = CUSTOM_DATA_PULLS.get(self.slug_or_file, DirectDataPull)
        self.data_pull_obj = data_pull_class(
            db_alias,
            query_file_path=self.slug_or_file,
            month=self.month, location_id=self.location_id
        )

    @prevent_parallel_execution(DATA_PULL_CACHE_KEY)
    def export(self):
        zip_file_name = "%s-DataPull.zip" % self.data_pull_obj.name
        with zipfile.ZipFile(zip_file_name, mode='w') as z:
            for filename, string_buffer in self.data_pull_obj.run().items():
                z.writestr(filename, string_buffer.getvalue())
        return zip_file_name

    @cached_property
    def queries(self):
        return self.data_pull_obj.get_queries()

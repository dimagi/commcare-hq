import os
import zipfile

from django.db import connections
from django.utils.functional import cached_property

from corehq.util.context_managers import prevent_parallel_execution
from custom.icds.const import DATA_PULL_CACHE_KEY
from custom.icds_reports.const import CUSTOM_DATA_PULLS
from custom.icds_reports.data_pull.exceptions import DataPullInProgressError


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
        self.db_alias = db_alias
        self.month = month
        self.location_id = location_id
        self.data_pull_obj = None
        self.custom_data_pull = False
        if self.slug_or_file in CUSTOM_DATA_PULLS:
            self.custom_data_pull = True
            data_pull_class = CUSTOM_DATA_PULLS[self.slug_or_file]
            self.data_pull_obj = data_pull_class(self.db_alias, month=self.month, location_id=self.location_id)
        self.result_file_name = None

    @prevent_parallel_execution(DATA_PULL_CACHE_KEY)
    def export(self):
        if self.slug_or_file in CUSTOM_DATA_PULLS:
            generated_files = self.data_pull_obj.run()
        else:
            generated_files = self._run_via_sql_file()
        if generated_files:
            self._zip_files(generated_files)
        return self.result_file_name

    def _run_via_sql_file(self):
        sql = self.queries[0].replace('\n', ' ')
        file_name = "%s-%s-%s.csv" % (self.slug_or_file.split('/')[-1], self.month, self.location_id)
        with open(file_name, "w") as output:
            db_conn = connections[self.db_alias]
            c = db_conn.cursor()
            c.copy_expert("COPY ({query}) TO STDOUT DELIMITER ',' CSV HEADER;".format(query=sql), output)
        return [file_name]

    def _zip_files(self, generated_files):
        if self.slug_or_file in CUSTOM_DATA_PULLS:
            zip_file_name = "%s-DataPull.zip" % CUSTOM_DATA_PULLS[self.slug_or_file].name
        else:
            zip_file_name = "%s-DataPull.zip" % self.slug_or_file.split('/')[-1]
        with zipfile.ZipFile(zip_file_name, mode='a') as z:
            for generated_file in generated_files:
                z.write(generated_file)
                os.remove(generated_file)
        self.result_file_name = zip_file_name

    @cached_property
    def queries(self):
        if self.data_pull_obj:
            return self.data_pull_obj.get_queries()
        else:
            with open(self.slug_or_file) as _sql:
                sql = _sql.read()
                return [sql.format(month=self.month, location_id=self.location_id)]

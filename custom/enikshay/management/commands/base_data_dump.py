# -*- coding: utf-8 -*-
from __future__ import absolute_import
import csv
import tempfile
from datetime import datetime

from django.core.management.base import BaseCommand
from django.urls import reverse

from couchexport.models import Format

from corehq.blobs import get_blob_db
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.files import safe_filename_header

from dimagi.utils.django.email import send_HTML_email
from dimagi.utils.web import get_url_base

from soil.util import expose_blob_download

DOMAIN = "enikshay"


class BaseDataDump(BaseCommand):
    TASK_NAME = ""
    INPUT_FILE_NAME = ""

    def __init__(self, *args, **kwargs):
        super(BaseDataDump, self).__init__(*args, **kwargs)
        self.log_progress = None
        self.result_file_name = None
        self.case_type = None
        self.input_file_name = None
        self.report = {}
        self.result_file_headers = []
        self.recipient = None

    def add_arguments(self, parser):
        parser.add_argument('--case-type', action='store_true')
        parser.add_argument('--recipient', type=str)

    def handle(self, case_type, recipient, *args, **options):
        self.case_type = case_type
        self.recipient = recipient
        if not self.recipient:
            return

        self.input_file_name = self.INPUT_FILE_NAME
        self.setup()
        temp_file_path = self.generate_dump()
        download_id = self.save_dump_to_blob(temp_file_path)
        self.email_result(download_id)

    def setup_result_file_name(self):
        result_file_name = "data_dumps_{case_type}_{timestamp}.csv".format(
            case_type=self.case_type,
            timestamp=datetime.now().strftime("%Y-%m-%d--%H-%M-%S"),
        )
        return result_file_name

    def setup(self):
        with open(self.input_file_name, 'rU') as input_file:
            reader = csv.DictReader(input_file)
            for row in reader:
                self.report[row['Column Name']] = {
                    row['Case Reference']: row['Calculation']
                }
                self.result_file_headers.append(row['Column Name'])
        self.result_file_name = self.setup_result_file_name()

    def include_case_in_dump(self, case):
        return True

    def generate_dump(self):
        _, temp_path = tempfile.mkstemp()
        with open(temp_path, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.result_file_headers)
            writer.writeheader()
            # iterate cases
            for case in self.get_cases(self.case_type):
                # store any references like last_episode or any data point
                # that might be needed repeatedly for the same case and is expensive call
                self.context = {}
                case_row = {}
                if not self.include_case_in_dump(case):
                    continue
                # iterate columns to be generated
                # details is a dict with key in [
                # "N/A" -> not to be populated so ignore it
                # self -> value would be a case property or some meta on the case itself
                # custom -> value would be some custom logic to be manually coded
                # specific case reference/association -> value would be case property on this associated case]
                for column_name, details in self.report.items():
                    for case_reference, calculation in details.items():
                        if case_reference == "N/A":
                            case_row[column_name] = "N/A"
                        elif case_reference == 'self':
                            if calculation == 'caseid':
                                case_row[column_name] = case.case_id
                            else:
                                column_value = case.get_case_property(calculation)
                                if column_value:
                                    column_value = column_value.encode("utf-8")
                                case_row[column_name] = column_value
                        elif case_reference == 'custom':
                            try:
                                case_row[column_name] = self.get_custom_value(column_name, case)
                            except Exception as e:
                                case_row[column_name] = str(e)
                        else:
                            try:
                                case_row[column_name] = self.get_case_reference_value(
                                    case_reference, case, calculation)
                            except Exception as e:
                                case_row[column_name] = str(e)

                writer.writerow(case_row)

        return temp_path

    def save_dump_to_blob(self, temp_path):
        with open(temp_path, 'rb') as file_:

            blob_db = get_blob_db()
            blob_db.put(
                file_,
                self.result_file_name,
                timeout=60 * 48)  # 48 hours

            file_format = Format.from_format(Format.CSV)
            file_name_header = safe_filename_header(
                self.result_file_name, file_format.extension)
            blob_dl_object = expose_blob_download(
                self.result_file_name,
                mimetype=file_format.mimetype,
                content_disposition=file_name_header
            )
        return blob_dl_object.download_id

    def email_result(self, download_id):
        url = "%s%s" % (get_url_base(),
                        reverse('ajax_job_poll', kwargs={'download_id': download_id}))
        send_HTML_email('%s Download for %s Finished' % (DOMAIN, self.case_type),
                        self.recipient,
                        'Simple email, just to let you know that there is a '
                        'download waiting for you at %s. It will expire in 48 hours' % url)

    def get_cases(self, case_type):
        case_accessor = CaseAccessors(DOMAIN)
        return case_accessor.iter_cases(self.get_case_ids(case_type))

    def get_case_ids(self, case_type):
        raise NotImplementedError

    def get_custom_value(self, column_name, case):
        raise NotImplementedError

    def get_case_reference_value(self, case_reference, case, calculation):
        raise NotImplementedError

# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
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
        self.notes = {}
        self.column_statuses = {}
        self.result_file_headers = []
        self.recipient = None
        self.full = False

    def add_arguments(self, parser):
        parser.add_argument('--recipient', type=str)
        parser.add_argument('--full', action='store_true', dest='full', default=False)

    def handle(self, recipient, *args, **options):
        self.recipient = recipient
        self.input_file_name = self.INPUT_FILE_NAME
        self.setup()
        temp_file_path = self.generate_dump()
        download_id = self.save_dump_to_blob(temp_file_path)
        self.email_result(download_id)

    def setup_result_file_name(self):
        result_file_name = "{dump_title}_{timestamp}.csv".format(
            dump_title=self.TASK_NAME,
            timestamp=datetime.now().strftime("%Y-%m-%d--%H-%M-%S"),
        )
        return result_file_name

    def setup(self):
        input_file_path = '%s/%s' % (os.path.dirname(os.path.realpath(__file__)),
                                     self.INPUT_FILE_NAME)
        with open(input_file_path, 'rU') as input_file:
            reader = csv.DictReader(input_file)
            for row in reader:
                self.report[row['Column Name']] = {
                    row['Case Reference']: row['Calculation']
                }
                self.notes[row['Column Name']] = row.get('Notes')
                self.column_statuses[row['Column Name']] = row.get('Column Status')
                self.result_file_headers.append(row['Column Name'])
        self.result_file_name = self.setup_result_file_name()

    def include_case_in_dump(self, case):
        return True

    def generate_dump(self):
        _, temp_path = tempfile.mkstemp()
        with open(temp_path, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.result_file_headers)
            writer.writeheader()
            writer.writerow(self.notes)
            writer.writerow(self.column_statuses)
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
            blob_db.put(file_, self.result_file_name, timeout=60 * 48)  # 48 hours

            file_format = Format.from_format(Format.CSV)
            blob_dl_object = expose_blob_download(
                self.result_file_name,
                mimetype=file_format.mimetype,
                content_disposition=safe_filename_header(self.result_file_name, file_format.extension),
            )
        return blob_dl_object.download_id

    def email_result(self, download_id):
        if not self.recipient:
            return
        url = reverse('ajax_job_poll', kwargs={'download_id': download_id})
        send_HTML_email('%s Download for %s Finished' % (DOMAIN, self.case_type),
                        self.recipient,
                        'Simple email, just to let you know that there is a '
                        'download waiting for you at %s' % url)

    def get_cases(self, case_type):
        case_accessor = CaseAccessors(DOMAIN)
        case_ids = self.get_case_ids(case_type)
        if not self.full:
            case_ids = case_ids[0:500]
        return case_accessor.iter_cases(case_ids)

    def get_case_ids(self, case_type):
        raise NotImplementedError

    def get_custom_value(self, column_name, case):
        raise NotImplementedError

    def get_case_reference_value(self, case_reference, case, calculation):
        raise NotImplementedError

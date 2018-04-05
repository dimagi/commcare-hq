# -*- coding: utf-8 -*-
from __future__ import (
    absolute_import,
    unicode_literals,
)
import csv
import os
import tempfile
from zipfile import ZipFile
from datetime import datetime

from django.core.management.base import BaseCommand
from django.urls import reverse

from couchexport.models import Format

from corehq.apps.locations.models import SQLLocation
from corehq.blobs import get_blob_db
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.files import safe_filename_header
from corehq.elastic import ES_EXPORT_INSTANCE
from corehq.apps.es.case_search import CaseSearchES

from dimagi.utils.django.email import send_HTML_email
from dimagi.utils.web import get_url_base

from soil.util import expose_blob_download
from casexml.apps.case.util import get_all_changes_to_case_property

from custom.enikshay.case_utils import (
    CASE_TYPE_PERSON,
)

DOMAIN = "enikshay"
LIMITED_TEST_DUMP_SIZE = 500
PRIVATE_SECTOR_ID_MAPPING = {
    '1': "PATH",
    '2': "MJK",
    '3': "Alert-India",
    '4': "WHP-Patna",
    '5': "DTO-Mehsana",
    '6': "Vertex",
    '7': "Accenture",
    '8': "BMGF",
    '9': "EY",
    '10': "CTD",
    '11': "Nagpur",
    '12': "Nagpur-rural",
    '13': "Nagpur_Corp",
    '14': "Surat",
    '15': "SMC",
    '16': "Surat_Rural",
    '17': "Rajkot",
    '18': "WHP-AMC"
}

PRIVATE_SECTOR_PERSON_CASE_IDS_TO_IGNORE = [
    "8f0608ef-b78d-4135-aef3-b857c8d7fb04",
    "81b43362-12c4-48f9-b705-a3618d9e5a59",
    "4f3c278b-945a-4dfa-99ea-632f4a329823",
    "48eecd28-a416-477a-a00c-307f665df65d",
    "17fb07d0-913c-40d1-911b-f2b923732ff2",
    "8123dac7-3a35-49be-8467-5f84c13f5473",
    "8a17015d-4dd0-4e9b-a754-11f49fe772aa",
    "90e271ec-fa21-4748-bc2b-09f395fa2080",
    "609990a2-34c2-4b1d-9788-8e37f7e5fe24",
    "bd077386-67a6-480a-850d-a9898a53104a",
    "7ce438c5-a374-42c3-8e73-8f2763a59aa3",
    "d3bb7e37-d51f-4891-a529-9a54fb8bdae7",
    "918f6b6e-7834-4141-ba21-41b5add03f1e",
    "20c68017-ef12-4bb8-b979-d131b0d3ff85",
    "cf83a73a-89e2-4b6a-b2e9-896b2b11df66",
    "3f1435cb-ee37-4b3d-8936-46c37cb792c4",
    "556006f9-ca1c-423a-80dd-f2e72492f6e6",
    "6330d4e0-666b-45a1-99a4-07f92fad8691",
    "8d1197cb-21f5-4f9b-846c-a0dbac07b9fc",
    "217f9232-3a1e-4160-9225-b47c8de9d2b2",
    "ae9ecff3-1b5c-42c5-a3ce-e0a3810f6906",
    "f3650c3f-eac4-49b7-973d-655bfd4a04e9",
    "2b6c8a3b-ee81-4948-94d8-18d6d8dffe86",
    "e6429add-06f2-4149-be30-d24c3586aa90"
]


class BaseDataDump(BaseCommand):
    TASK_NAME = ""
    INPUT_FILE_NAME = ""

    def __init__(self, *args, **kwargs):
        super(BaseDataDump, self).__init__(*args, **kwargs)
        self.log_progress = None
        self.result_file_name = None
        self.case_type = None
        self.report = {}
        self.notes = {"Column Name": "Notes"}
        self.column_statuses = {"Column Name": "Column Status"}
        self.result_file_headers = ["Column Name"]
        self.recipient = None
        self.full = False
        self.case_search_instance = CaseSearchES(es_instance_alias=ES_EXPORT_INSTANCE).domain(DOMAIN)

    def add_arguments(self, parser):
        parser.add_argument('--recipient', type=str)
        parser.add_argument('--full', action='store_true', dest='full', default=False)

    def handle(self, recipient, *args, **options):
        self.recipient = recipient
        self.full = options.get('full')
        if not self.recipient:
            return

        self.full = options.get('full')
        self.setup()
        temp_file_path = self.generate_dump()
        temp_zip_path = self.zip_dump(temp_file_path)
        download_id = self.save_dump_to_blob(temp_zip_path)
        self.clean_temp_files(temp_file_path, temp_zip_path)
        self.email_result(download_id)

    def setup_result_file_name(self):
        result_file_name = "enikshay_data_public_{dump_title}_{timestamp}_{full}.csv".format(
            dump_title=self.TASK_NAME,
            timestamp=datetime.now().strftime("%Y-%m-%d--%H-%M-%S"),
            full=('full' if self.full else 'mock')
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
            writer.writerow({"Column Name": "Data begins after this row"})
            # iterate cases
            for case in self.get_cases(self.case_type):
                # store any references like last_episode or any data point
                # that might be needed repeatedly for the same case and is expensive call
                self.context = {}
                case_row = {}
                if not self.include_case_in_dump(case):
                    continue
                for case_to_dump in self.cases_to_dump(case):
                    # iterate columns to be generated
                    # details is a dict with key in [
                    # "N/A" -> not to be populated so ignore it
                    # self -> value would be a case property or some meta on the case itself
                    # custom -> value would be some custom logic to be manually coded
                    # specific case reference/association -> value would be case property on this associated case]
                    for column_name, details in self.report.items():
                        for case_reference, calculation in details.items():
                            if case_reference == "N/A":
                                case_row[column_name] = ""
                            elif case_reference in ['self', 'Self']:
                                if calculation == 'caseid':
                                    case_row[column_name] = case_to_dump.case_id
                                else:
                                    column_value = case_to_dump.get_case_property(calculation)
                                    if column_value and not isinstance(column_value, bool):
                                        column_value = column_value.encode("utf-8")
                                    case_row[column_name] = column_value
                            elif case_reference == 'custom':
                                try:
                                    case_row[column_name] = self.get_custom_value(column_name, case_to_dump)
                                except Exception as e:
                                    case_row[column_name] = str(e)
                            else:
                                try:
                                    column_value = self.get_case_reference_value(
                                        case_reference, case_to_dump, calculation)
                                    if column_value and not isinstance(column_value, bool):
                                        column_value = column_value.encode("utf-8")
                                    case_row[column_name] = column_value
                                except Exception as e:
                                    case_row[column_name] = str(e)

                    writer.writerow(case_row)

        return temp_path

    def zip_dump(self, temp_file_path):
        _, zip_temp_path = tempfile.mkstemp(".zip")
        with ZipFile(zip_temp_path, 'w') as zip_file_:
            zip_file_.write(temp_file_path, self.result_file_name)

        return zip_temp_path

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

    def clean_temp_files(self, *temp_file_paths):
        for file_path in temp_file_paths:
            os.remove(file_path)

    def email_result(self, download_id):
        url = "%s%s?%s" % (get_url_base(),
                           reverse('retrieve_download', kwargs={'download_id': download_id}),
                           "get_file")  # downloads immediately, rather than rendering page
        send_HTML_email(
            '[%s] [%s] Export ready for %s.' % (
                DOMAIN,
                'Full' if self.full else 'Mock',
                self.TASK_NAME),
            self.recipient,
            'Simple email, just to let you know that there is a '
            'download waiting for you at %s. It will expire in 48 hours' % url)

    def get_cases(self, case_type):
        case_accessor = CaseAccessors(DOMAIN)
        case_ids_query = self.get_case_ids_query(case_type)
        if not self.full:
            case_ids_query = case_ids_query.size(LIMITED_TEST_DUMP_SIZE)
        case_ids = case_ids_query.get_ids()
        return case_accessor.iter_cases(case_ids)

    def cases_to_dump(self, case):
        return [case]

    def get_case_ids_query(self, case_type):
        raise NotImplementedError

    def get_custom_value(self, column_name, case):
        raise NotImplementedError

    def get_case_reference_value(self, case_reference, case, calculation):
        raise NotImplementedError

    @staticmethod
    def case_property_change_info(test_case, case_property_name, case_property_value):
        all_changes = get_all_changes_to_case_property(test_case, case_property_name)

        changes_for_value = [change for change in all_changes
                             if change.new_value == case_property_value]

        if len(changes_for_value) > 1:
            raise Exception("Case Property %s set as %s by multiple users on case %s" % (
                case_property_name, case_property_value, test_case.case_id
            ))
        elif len(changes_for_value) == 1:
            return changes_for_value[0]
        else:
            raise Exception("Case Property not %s set as %s by any user on case %s" % (
                case_property_name, case_property_value, test_case.case_id
            ))

    @staticmethod
    def person_belongs_to_real_location(person_case):
        if person_case.case_id in PRIVATE_SECTOR_PERSON_CASE_IDS_TO_IGNORE:
            print("ignoring person case %s" % person_case.case_id)
            return False
        assert person_case.type == CASE_TYPE_PERSON
        try:
            owner_id = person_case.owner_id
            owner_location = SQLLocation.active_objects.get(location_id=owner_id)
            return owner_location.metadata['is_test'] != "yes"
        except SQLLocation.DoesNotExist:
            return True

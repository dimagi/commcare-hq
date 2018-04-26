from __future__ import absolute_import
from __future__ import print_function
import csv
from corehq.apps.es import queries
from corehq.apps.locations.models import SQLLocation

from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    CASE_TYPE_ADHERENCE,
    get_person_case_from_episode,
    get_episode_case_from_adherence,
    get_adherence_cases_from_episode,
)
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
)
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.management.commands.base_data_dump import (
    BaseDataDump,
    LIMITED_TEST_DUMP_SIZE,
    PRIVATE_SECTOR_ID_MAPPING,
)
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from dimagi.utils.chunked import chunked
from datetime import datetime


DOMAIN = "enikshay"


class Command(BaseDataDump):
    """
    09. Record Adherence
    https://docs.google.com/spreadsheets/d/1t6cd-VPy6p8EOEhQJD15IbULU0EJ05ALQ0tcdfx6ng8/edit#gid=1444087620&range=A42
    """
    TASK_NAME = "09_record_adherence"
    INPUT_FILE_NAME = "data_dumps_private_record_adherence.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_EPISODE

    def handle(self, recipient, *args, **options):
        self.recipient = recipient
        self.full = options.get('full')
        if not self.recipient:
            return

        self.full = options.get('full')
        self.setup()
        temp_file_path = self.generate_dump()
        # temp_zip_path = self.zip_dump(temp_file_path)
        # download_id = self.save_dump_to_blob(temp_zip_path)
        # self.clean_temp_files(temp_file_path, temp_zip_path)
        # self.email_result(download_id)

    def get_cases(self, case_type):
        raise NotImplementedError

    def generate_dump(self):
        # iterate cases
        case_accessor = CaseAccessors(DOMAIN)
        case_ids_query = self.get_case_ids_query(self.case_type)
        if not self.full:
            case_ids_query = case_ids_query.size(LIMITED_TEST_DUMP_SIZE)
        all_case_ids = case_ids_query.get_ids()
        index = 0
        for chunk in chunked(all_case_ids, 52500):
            index += 1
            result_file_name = "enikshay_data_public_{dump_title}_{timestamp}_{full}_{index}.csv".format(
                dump_title=self.TASK_NAME,
                timestamp=datetime.now().strftime("%Y-%m-%d--%H-%M-%S"),
                full=('full' if self.full else 'mock'),
                index=index
            )
            print("starting index {index}".format(index=index))
            with open(result_file_name, 'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.result_file_headers)
                writer.writeheader()
                writer.writerow(self.notes)
                writer.writerow(self.column_statuses)
                writer.writerow({"Column Name": "Data begins after this row"})
                for case in case_accessor.iter_cases(chunk):
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
            print("finished index {index}".format(index=index))

    def get_case_ids_query(self, case_type):
        """
        all adherence cases
        with person.dataset = 'real' and person.enrolled_in_private != 'true'
        """
        return (self.case_search_instance
                .case_type(case_type)
                .case_property_query(ENROLLED_IN_PRIVATE, 'true', clause=queries.MUST)
                )

    def include_case_in_dump(self, episode):
        assert episode.type == CASE_TYPE_EPISODE
        try:
            person = self.get_person(episode)
        except ENikshayCaseNotFound:
            return False
        return (
            person and
            person.get_case_property('dataset') == 'real' and
            person.get_case_property(ENROLLED_IN_PRIVATE) == 'true' and
            self.person_belongs_to_real_location(person)
        )

    def cases_to_dump(self, episode_case):
        assert episode_case.type == CASE_TYPE_EPISODE
        return get_adherence_cases_from_episode(DOMAIN, episode_case.case_id)

    def get_custom_value(self, column_name, adherence):
        assert adherence.type == CASE_TYPE_ADHERENCE, \
            "Unexpected Case type instead of %s" % CASE_TYPE_ADHERENCE
        if column_name == "eNikshay person UUID":
            person_case = self.get_person(adherence)
            return person_case.case_id
        elif column_name == "eNikshay episode UUID":
            episode_case = self.get_episode(adherence)
            return episode_case.case_id
        elif column_name == "Organisation":
            owner_id = self.get_person(adherence).owner_id
            location = SQLLocation.active_objects.get_or_None(location_id=owner_id)
            if location:
                private_sector_org_id = location.metadata.get('private_sector_org_id')
                if private_sector_org_id:
                    return PRIVATE_SECTOR_ID_MAPPING.get(private_sector_org_id, private_sector_org_id)
                else:
                    raise Exception("Private Sector Organization ID not set for location %s" % owner_id)
            else:
                raise Exception("Location not found for id %s" % owner_id)
        raise Exception("unknown custom column %s" % column_name)

    def get_person(self, adherence):
        assert adherence.type in [CASE_TYPE_ADHERENCE, CASE_TYPE_EPISODE], \
            "Unexpected Case type instead of %s and %s" % (CASE_TYPE_ADHERENCE, CASE_TYPE_EPISODE)

        if 'person' not in self.context:
            if adherence.type == CASE_TYPE_EPISODE:
                episode = adherence
            else:
                episode = self.get_episode(adherence)
            self.context['person'] = get_person_case_from_episode(DOMAIN, episode.case_id)
        return self.context['person']

    def get_episode(self, adherence):
        assert adherence.type == CASE_TYPE_ADHERENCE
        if 'episode' not in self.context:
            self.context['episode'] = get_episode_case_from_adherence(DOMAIN, adherence.case_id)
        return self.context['episode']

    def get_case_reference_value(self, case_reference, adherence, calculation):
        if case_reference == 'person':
            return self.get_person(adherence).get_case_property(calculation)
        elif case_reference == 'episode':
            return self.get_episode(adherence).get_case_property(calculation)
        return Exception("unknown case reference %s" % case_reference)

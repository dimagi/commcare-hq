from xml.etree import cElementTree as ElementTree

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.apps.locations.models import SQLLocation
from custom.covid.management.commands.update_cases import CaseUpdateCommand

BATCH_SIZE = 100
DEVICE_ID = __name__ + ".update_owner_ids"
CHILD_LOCATION_TYPE = 'investigators'


class Command(CaseUpdateCommand):
    help = f"Changes the owner_id of a case to the location_id of the child location with type " \
           f"{CHILD_LOCATION_TYPE} of the current location"

    def case_block(self, case, child_location):
        return ElementTree.tostring(CaseBlock.deprecated_init(
            create=False,
            case_id=case.case_id,
            owner_id=child_location.location_id,
        ).as_xml(), encoding='utf-8').decode('utf-8')

    def update_cases(self, domain, case_type, user_id):
        case_ids = self.find_case_ids_by_type(domain, case_type)
        accessor = CaseAccessors(domain)

        locations_objects = {}
        case_blocks = []
        errors = []
        skip_count = 0
        for case in accessor.iter_cases(case_ids):
            owner_id = case.get_case_property('owner_id')
            if owner_id in locations_objects:
                location_obj = locations_objects[owner_id]
            else:
                try:
                    location_obj = SQLLocation.objects.get(location_id=owner_id)
                except SQLLocation.DoesNotExist:
                    errors.append("Location does not exist associated with the owner_id:{}. "
                                  "Case:{}".format(owner_id, case.case_id))
                    skip_count += 1
                    continue
                locations_objects[owner_id] = location_obj
            if location_obj:
                children = location_obj.get_children()
                has_correct_child_location_type = False
                for child_location in children:
                    if child_location.location_type.code == CHILD_LOCATION_TYPE:
                        case_blocks.append(self.case_block(case, child_location))
                        has_correct_child_location_type = True
                        break
                if not has_correct_child_location_type:
                    skip_count += 1
            else:
                skip_count += 1
        print(f"{len(case_blocks)} to update in {domain}, {skip_count} cases have skipped due to unknown owner_id"
              f" or has no child location of type {CHILD_LOCATION_TYPE}.")

        total = 0
        for chunk in chunked(case_blocks, BATCH_SIZE):
            submit_case_blocks(chunk, domain, device_id=DEVICE_ID, user_id=user_id)
            total += len(chunk)
            print("Updated {} cases on domain {}".format(total, domain))

        self.log_data(domain, "update_owner_ids", case_type, len(case_ids), total, errors)

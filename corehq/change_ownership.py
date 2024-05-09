from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase
from corehq.apps.locations.models import SQLLocation
from corehq.apps.es import CaseSearchES
from corehq.apps.es.cases import case_type
import os
import time
import math

from casexml.apps.case.mock import CaseBlock
from corehq.apps.hqcase.utils import submit_case_blocks

# DOMAIN = 'alafiacomm'
DOMAIN = 'alafiacomm-prod'

success_case_log_file_path = os.path.expanduser('~/script_success.log')
error_case_log_file_path = os.path.expanduser('~/script_error.log')

BATCH_SIZE = 100
SKIP_COUNT = 0

def submit_case_blocks(case_blocks):
    submit_case_blocks(
        [cb.as_text() for cb in case_blocks],
        domain=DOMAIN,
        device_id='system',
    )

def write_to_log(ids, is_success=True, message=None):
    if is_success:
        file_path = success_case_log_file_path
    else:
        file_path = error_case_log_file_path
    with open(file_path, 'a') as log:
        for id in ids:
            log.write(
                'Skipped ' if not is_success else '' \
                f'{id} - ' \
                'Reason:' + message if message else ''
            )
        log.close()

def process_batch(case_blocks, current_chunk, total_count):
    batch_start = current_chunk * BATCH_SIZE + 1
    batch_end = batch_start + len(case_blocks)
    percentage_done = round((batch_start / total_count) * 100, 2)
    print(f'Submitting cases {batch_start}-{batch_end}/{total_count} ({percentage_done}%)')
    try:
        submit_case_blocks(case_blocks)
        write_to_log([cb.case_id for cb in case_blocks])
        return True
    except Exception as e:
        write_to_log(
            [cb.case_id for cb in case_blocks],
            is_success=False,
            message=str(e)
        )
        return False

### Task 1
def move_mobile_workers():
    print("---MOVING MOBILE WORKER LOCATIONS---")
    RC_NUM_PROP_NAME = 'rc_number'
    USER_TYPE_PROP_NAME = 'usertype'

    users = CommCareUser.by_domain(DOMAIN)
    user_count = len(users)
    success_count = fail_count = skip_count = 0
    total_time = 0
    print(f"Total Users to Process: {user_count}")
    user_to_save = []
    for idx, user in enumerate(users):
        start_time = time.time()
        percentage_done = round((idx / user_count) * 100, 2)
        print(f'Processing User {idx}/{user_count} ({percentage_done}%)')

        # First make sure that the user type is rc
        user_data = user.get_user_data(DOMAIN)
        if user_data[USER_TYPE_PROP_NAME] != 'rc':
            write_to_log([user.user_id], is_success=False, message="User Type not RC")
            skip_count += 1
            continue

        try:
            # Get a descendant of user location which has the same rc number
            loc = SQLLocation.objects.get(
                domain=DOMAIN,
                parent__location_id=user.location_id,
                name=user_data[RC_NUM_PROP_NAME]
            )
            # Set this new descendant location as user location
            user.location_id = loc.location_id
            user_to_save.append(user)
            write_to_log([user.user_id])
            success_count += 1
        except SQLLocation.DoesNotExist:
            write_to_log(
                [user.user_id],
                is_success=False,
                message=f'({user_data[RC_NUM_PROP_NAME]}) does not exist as child of location with id ({loc.location_id})'
            )
            fail_count += 1
        finally:
            # Time logging
            end_time = time.time()
            time_diff = end_time - start_time
            total_time += time_diff
            print(f'Time to process User #{idx}: {time_diff}s')
            print(f'Estimate time remaining: {time_diff * (user_count - idx)}s')

        print("Processing Users Complete!")
        print(
            f"Success: {success_count}, 
            Fail: {fail_count}, 
            Skipped: {skip_count},
            Total Time: {round(total_time / 60, 2)} minutes"
        )
    CommCareUser.bulk_save(user_to_save)
    print("Saving Users Complete!")

### Task 2 & 3
def transfer_case_ownership():
    print("---MOVING CASE OWNERSHIP---")
    case_ids = (
        CaseSearchES()
        .domain(DOMAIN)
        .OR(
            case_type('menage'),
            case_type('membre'),
            case_type('seance_educative'),
            case_type('fiche_pointage')
        )
        .sort('opened_on')  # sort so that we can continue
    ).get_ids()

    case_count = len(case_ids)
    batch_count = math.ceil(case_count / BATCH_SIZE)
    print(f'Total Cases to Process: {case_count}')
    print(f'Total Batches to Process: {batch_count}')
    case_blocks = []
    current_chunk = 0
    start_time = end_time = total_time = 0
    success_count = fail_count = 0
    for case_obj in CommCareCase.objects.iter_cases(case_ids, domain=DOMAIN):
        try:
            user = CommCareUser.get_by_user_id(case_obj.opened_by)
        except CommCareUser.AccountTypeError as e:
            write_to_log([case_obj.case_id], is_success=False, message='Not a mobile worker account')
            fail_count += 1
            continue
        else:
            case_block = CaseBlock(
                create=False,
                case_id=case_obj.case_id,
                owner_id=user.location_id,
            )
            case_blocks.append(case_block)

        # Process and submit batch of cases
        if len(case_blocks) == BATCH_SIZE:
            is_success = process_batch(case_blocks, current_chunk, case_count)
            if is_success:
                success_count += 1
            else:
                fail_count += 1
            end_time = time.time()
            time_diff = end_time - start_time
            total_time += time_diff
            print(f'Time to Process Batch #{current_chunk}: {time_diff}s')
            print(f'Estimated time remaining: {time_diff * (batch_count - current_chunk)}s')
            case_blocks = []
            current_chunk += 1
            start_time = time.time()
    
    # Submit any remaining cases after processing the last full batch
    if len(case_blocks):
        process_batch(case_blocks, current_chunk, case_count)

    print("All Cases Done Processing!")
    print(
        f"Successful batches: {success_count}, 
        Failed batches: {fail_count}, 
        Total Batches: {batch_count}, 
        Total Time: {round(total_time / 60, 2)} minutes"
    )


success_count = fail_count = 0
for user in valid_users:
    user_data = user.get_user_data(DOMAIN)
    try:
        loc = SQLLocation.objects.get(
            domain=DOMAIN,
            parent__location_id=user.location_id,
            name=user_data['rc_number']
        )
    except SQLLocation.DoesNotExist:
        fail_count += 1
    else:
        success_count += 1
print(success_count, fail_count)
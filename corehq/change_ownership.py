from corehq.apps.users.models import CommCareUser
from corehq.apps.locations.models import SQLLocation
import os
import time
DOMAIN = 'alafiacomm-prod'

success_case_log_file_path = os.path.expanduser('~/script_success.log')
error_case_log_file_path = os.path.expanduser('~/script_error.log')

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
            user.save(fire_signals=False)
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

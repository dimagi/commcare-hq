from corehq.apps.es import cases as case_es
from corehq.apps.es.forms import FormES
from corehq.form_processor.models.forms import XFormInstance
import datetime
from math import ceil
import os

# Note: There are over 2.3 million cases that need to be archived on the target project. For this reason,
# batching will be necessary. Furthermore, the batch sizes are kept small as each case can have 2-3+ forms
# that will need to be archived.

# Constants
DOMAIN = 'test-65' # 'fmoh-echis-staging'
DATE_CONSTRAINT = datetime.date(2022, 5, 1)
BATCH_SIZE = 100
ERROR_LOG_FILE_PATH = os.path.expanduser("~/zeng_script_error.log")
SUCCESS_LOG_FILE_PATH = os.path.expanduser("~/zeng/script_success.log")

# Get the total number of cases to process
total_cases = (
    case_es.CaseES()
    .domain(DOMAIN)
    .OR(
        case_es.is_closed(True),
        case_es.opened_range(lt=DATE_CONSTRAINT)
    )
    .count()
)
batch_count = ceil(total_cases / BATCH_SIZE)
print(f"Total of {total_cases} cases to process over {batch_count} batches")

def process_batch(batch_number):
    start_count = batch_number * BATCH_SIZE
    percent_complete = int(start_count / total_cases)
    print(f"Processing {start_count}-{BATCH_SIZE * (batch_number + 1)} ({percent_complete}%)")

    # Get all relevant cases
    closed_or_old_case_ids = (
        case_es.CaseES()
        .domain(DOMAIN)
        .OR(
            case_es.is_closed(True),
            case_es.opened_range(lt=DATE_CONSTRAINT)
        )
        .start(start_count)
        .size(BATCH_SIZE)
        .values_list('_id', flat=True)
    )

    # Get related form ids from case ids
    form_ids = (
        FormES()
        .domain(DOMAIN)
        .updating_cases(closed_or_old_case_ids)
        .values_list('_id', flat=True)
    )

    # Turn into XFormInstances and archive each form
    forms_to_archive = XFormInstance.objects.get_forms(form_ids=form_ids)
    failed_count = 0
    total_count = len(forms_to_archive)
    successful_forms = []
    failed_forms = {}
    for index, form in enumerate(forms_to_archive):
        print(f"Archiving form ({index + 1}/{total_count})")
        try:
            form.archive()
            successful_forms.append(form.id)
        except Exception as e:
            print(f"Failed to archive form with id {form.id}:", repr(e))
            failed_forms[form.id] = repr(e)
            failed_count += 1
    print(f"Finished archiving with {failed_count} errors")
    return successful_forms, failed_forms


def write_status_to_file(success, failed):
    with open(SUCCESS_LOG_FILE_PATH, "a") as success_log:
        for id in success:
            success_log.write(f"{id}\n")
    with open(ERROR_LOG_FILE_PATH, "a") as error_log:
        for key, value in failed.items:
            error_log.write(f"{key}: {value}\n")


 # +1 since range() is exclusive of end range
for batch_number in range(batch_count + 1):
    success, failed = process_batch(batch_number)
    write_status_to_file(success, failed)

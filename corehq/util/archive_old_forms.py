from corehq.apps.es import cases as case_es
from corehq.apps.es.forms import FormES
from corehq.form_processor.models.forms import XFormInstance
import datetime
from math import ceil

# Note: There are over 2.3 million cases that need to be archived on the target project. For this reason,
# batching will be necessary. Furthermore, the batch sizes are kept small as each case can have 2-3+ forms
# that will need to be archived.

# Constants
DOMAIN = 'test-65' # 'fmoh-echis-staging'
DATE_CONSTRAINT = datetime.date(2022, 5, 1)
BATCH_SIZE = 100

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

def process_batch(batch_number, failed_forms):
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
    #? Should we stop processing entirely when we hit an error?
    forms_to_archive = XFormInstance.objects.get_forms(form_ids=form_ids)
    failed_count = 0
    total_count = len(forms_to_archive)
    for index, form in enumerate(forms_to_archive):
        print(f"Archiving form ({index + 1}/{total_count})")
        try:
            form.archive()
        except Exception as e:
            print(f"Failed to archive form with id {form.id}:", repr(e))
            failed_forms[form.id] = repr(e)
            failed_count += 1
    print(f"Finished archiving with {failed_count} errors")

 # +1 since range() is exclusive of end range
failed_forms = {}
for batch_number in range(batch_count + 1):
    process_batch(batch_number, failed_forms)

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked
import csv
import os
import uuid
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.models import CommCareCase

DOMAIN = 'polio-rdc'
FILENAME = os.path.expanduser('~/polio_data/polio_cases_to_clone.csv') #! Rename this to current batch file
SUCCESS_FILENAME = os.path.expanduser('~/polio_data/polio_success_cases.log')
FAILED_FILENAME = os.path.expanduser('~/polio_data/polio_failed_cases.log')
CHUNK_SIZE = 100
BATCH_SIZE = 10000

# Split the original CSV file containing 100k cases into smaller csv files of 10k cases each
def batch_split():
    with open(FILENAME) as csvfile:
        reader = csv.reader(csvfile)
        batch_number = 1
        for rows in chunked(reader, BATCH_SIZE):
            out_file_name = f"polio_batch_{batch_number}.csv"
            filename = os.path.expanduser(f'~/polio_batches/{out_file_name}')
            with open(filename, mode='a') as out_file:
                for row in rows:
                    out_file.write(f'{row[0]},{row[1]}\n')
            batch_number += 1

# Clone case data by creating new cases containing same data
def process_chunk(case_ids):
    cases_to_create = []
    processed_old_case_ids = set()
    processed_cloned_case_ids = []
    for case_obj in CommCareCase.objects.iter_cases(case_ids, domain=DOMAIN):
        case_props = case_obj.case_json
        case_props['old_case_id'] = case_obj.case_id
        clone_case_id = uuid.uuid4().hex
        cases_to_create.append(
            CaseBlock(
                create=True,
                case_id=clone_case_id,
                case_name=case_obj.name,
                case_type=case_obj.type,
                date_opened=case_obj.opened_on,
                owner_id=case_obj.owner_id,
                user_id=case_obj.user_id,
                update=case_props,
            ).as_text()
        )
        processed_cloned_case_ids.append(f'{case_obj.case_id} -> {clone_case_id}')
        processed_old_case_ids.add(case_obj.case_id)
    submit_case_blocks(cases_to_create, DOMAIN, device_id='system')
    
    skipped_case_ids = set(case_ids) - processed_old_case_ids
    return skipped_case_ids, processed_cloned_case_ids


def process_chunk_logs(rows, filename, message=''):
    with open(filename, mode='a') as logfile:
        for case_id in rows:
            logfile.write(f'{case_id} - {message}\n')


def process_batch():
    with open(FILENAME) as csvfile:
        # File will contain a batch of 10k cases
        reader = csv.reader(csvfile)
        current_chunk = 1
        total_fail_count = 0
        total_skip_count = 0
        for rows in chunked(reader, CHUNK_SIZE):
            case_ids = [case_row[0] for case_row in rows]
            start_count = CHUNK_SIZE * (current_chunk - 1)
            print(f"Processing chunk {current_chunk} ({start_count + 1}-{start_count + len(case_ids)})")
            try:
                skipped_case_ids, processed_case_ids = process_chunk(case_ids)
                if len(skipped_case_ids):
                    total_skip_count += len(skipped_case_ids)
                    process_chunk_logs(skipped_case_ids, FAILED_FILENAME, message='Case does not exist')
                process_chunk_logs(processed_case_ids, SUCCESS_FILENAME)
            except Exception as e:
                print(f"Failed processing chunk {current_chunk}!")
                print(str(e))
                process_chunk_logs(case_ids, FAILED_FILENAME, message=str(e))
                total_fail_count += len(case_ids)
            current_chunk += 1
    print("Finished cloning batch of cases.")
    print(f"Failed: {total_fail_count} Skipped: {total_skip_count}")

from __future__ import absolute_import
from __future__ import print_function
import csv

from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from corehq.util.log import with_progress_bar
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.repeaters.models import Repeater, RepeatRecord
from corehq.motech.repeaters.dbaccessors import iter_repeat_records_by_domain, get_repeat_record_count
from custom.enikshay.integrations.utils import is_valid_episode_submission
from six.moves import input

domain = 'enikshay'


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.writer = None
        self.fire_in_place = False
        self.dry_run = False

    def add_arguments(self, parser):
        parser.add_argument(
            '--source_repeater_id',
            dest='source_repeater_id',
            help="Id for the repeater whose repeat records are to be re-triggered",
        )
        parser.add_argument(
            '--dest_repeater_id',
            dest='dest_repeater_id',
            help="If passed new repeat records would be added for this repeater",
        )
        parser.add_argument(
            '--state',
            dest='state',
            help='State of Records that are to be re-triggered: CANCELLED, SUCCESS, PENDING, FAIL',
        )
        parser.add_argument(
            '--dry_run',
            dest='dry_run',
            action='store_true',
            help='Pass this argument to get a report without making any real changes',
        )

    def handle(self, *args, **options):
        source_repeater_id = options.get('source_repeater_id')
        dest_repeater_id = options.get('dest_repeater_id')
        state = options.get('state')
        self.dry_run = options.get('dry_run')

        if self.dry_run:
            print("This is a dry run and nothing would be added or changed.")

        if source_repeater_id and not dest_repeater_id:
            self.fire_in_place = True
            proceed = input("""
                   Confirm to retrigger repeat records for repeater id: {repeater_id} for {state}.
                   This would be a retrigger in place and not async. Result will be stored in a csv file for
                   reference later (enter "yes" to proceed).
                """.format(
                repeater_id=source_repeater_id,
                state=state if state else 'ALL states'
            ))
        elif source_repeater_id and dest_repeater_id:
            proceed = input("""
                   Confirm to retrigger repeat records for repeater id: {repeater_id} for {state}.
                   This would add new repeat records for {dest_repeater_id} with payload id from the former repeat
                   record. Result will be stored in a csv file for reference later (enter "yes" to proceed).
                """.format(
                repeater_id=source_repeater_id,
                dest_repeater_id=dest_repeater_id,
                state=state if state else 'ALL states'
            ))
        else:
            raise CommandError("Insufficient arguments")

        if proceed == 'yes':
            print("Alright! Lets begin.")
            result_buffer = self.setup_result_file()
            if self.fire_in_place:
                self.fire_repeat_records_in_place(source_repeater_id, state)
            else:
                self.create_repeat_records_on_dest_repeater(source_repeater_id, dest_repeater_id, state)
            result_buffer.close()
        else:
            print("Mission Aborted!")

    def setup_result_file(self):
        result_file = "retrigger_stats_{ts}.csv".format(ts=datetime.now().strftime("%Y-%m-%d-%H-%M-%S"))
        result_buffer = open(result_file, 'w')
        fieldnames = self.get_header()
        self.writer = csv.DictWriter(result_buffer, fieldnames=fieldnames)
        self.writer.writeheader()
        print("File {filename} added. You can tail details there while the task is in progress".format(
            filename=result_file))
        return result_buffer

    def get_header(self):
        if self.fire_in_place:
            return ['rr_id', 'payload_id', 'migrated', 'succeeded', 'cancelled', 'failure_reason', 'error']
        else:
            return ['rr_id', 'payload_id', 'migrated', 'new_rr_id', 'error']

    def add_row(self, repeat_record, migrated, new_repeat_record_id=None):
        if self.fire_in_place:
            self.writer.writerow({
                'rr_id': repeat_record.get_id,
                'payload_id': repeat_record.payload_id,
                'migrated': migrated,
                'succeeded': repeat_record.succeeded,
                'cancelled': repeat_record.cancelled,
                'failure_reason': repeat_record.failure_reason,
            })
        else:
            self.writer.writerow({
                'rr_id': repeat_record.get_id,
                'payload_id': repeat_record.payload_id,
                'migrated': migrated,
                'new_rr_id': new_repeat_record_id,
            })

    def record_failure(self, repeat_record_id, payload_id, error_message):
        self.writer.writerow({
            'rr_id': repeat_record_id,
            'payload_id': payload_id,
            'error': error_message,
        })

    def fire_repeat_records_in_place(self, source_repeater_id, state):
        records = iter_repeat_records_by_domain(domain, repeater_id=source_repeater_id, state=state)
        record_count = get_repeat_record_count(domain, repeater_id=source_repeater_id, state=state)
        accessor = CaseAccessors(domain)
        retriggered = set()
        print("Iterating over records and firing them")
        for record in with_progress_bar(records, length=record_count):
            if record.payload_id in retriggered:
                self.record_failure(record.get_id, record.payload_id, error_message="Already triggered")
                continue
            try:
                episode = accessor.get_case(record.payload_id)
                episode_case_properties = episode.dynamic_case_properties()
                if (episode_case_properties.get('nikshay_registered', 'false') == 'false'
                        and episode_case_properties.get('private_nikshay_registered', 'false') == 'false'
                        and not episode_case_properties.get('nikshay_id')
                        and episode_case_properties.get('episode_type') == 'confirmed_tb'
                        and is_valid_episode_submission(episode)):
                    if not self.dry_run:
                        if record.next_check is None:
                            record.next_check = datetime.utcnow()
                        record.fire(force_send=True)
                    retriggered.add(record.payload_id)
                    self.add_row(record, episode_case_properties.get('migration_created_case'))
                else:
                    self.record_failure(record.get_id, record.payload_id, error_message="Not to be re-triggered")
            except Exception as e:
                self.record_failure(
                    record.get_id, record.payload_id,
                    error_message="{error}: {message}".format(error=e.__name__, message=e.message)
                )

    def create_repeat_records_on_dest_repeater(self, source_repeater_id, dest_repeater_id, state):
        dest_repeater = Repeater.get(dest_repeater_id)
        retriggered = set()

        records = iter_repeat_records_by_domain(domain, repeater_id=source_repeater_id, state=state)
        record_count = get_repeat_record_count(domain, repeater_id=source_repeater_id, state=state)
        accessor = CaseAccessors(domain)
        print("Iterating over records and adding new record for them")
        for record in with_progress_bar(records, length=record_count):
            if record.payload_id in retriggered:
                self.record_failure(record.get_id, record.payload_id, error_message="Already triggered")
                continue
            try:
                episode = accessor.get_case(record.payload_id)
                episode_case_properties = episode.dynamic_case_properties()
                if (episode_case_properties.get('nikshay_registered', 'false') == 'false'
                        and episode_case_properties.get('private_nikshay_registered', 'false') == 'false'
                        and not episode_case_properties.get('nikshay_id')
                        and episode_case_properties.get('episode_type') == 'confirmed_tb'
                        and is_valid_episode_submission(episode)):
                    new_record = RepeatRecord(
                        domain=domain,
                        next_check=datetime.utcnow(),
                        repeater_id=dest_repeater_id,
                        repeater_type=dest_repeater.doc_type,
                        payload_id=record.payload_id,
                    )
                    if not self.dry_run:
                        new_record.save()
                    retriggered.add(record.payload_id)
                    self.add_row(record, episode_case_properties.get('migration_created_case'), new_record.get_id)
                else:
                    self.record_failure(record.get_id, record.payload_id, error_message="Not to be re-triggered")
            except Exception as e:
                self.record_failure(
                    record.get_id, record.payload_id,
                    error_message="{error}: {message}".format(error=e.__name__, message=e.message)
                )

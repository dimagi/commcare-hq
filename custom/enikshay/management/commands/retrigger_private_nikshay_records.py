from datetime import datetime
from django.core.management.base import BaseCommand
from corehq.util.log import with_progress_bar
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.exceptions import CaseNotFound
from corehq.motech.repeaters.models import Repeater, RepeatRecord
from corehq.motech.repeaters.dbaccessors import iter_repeat_records_by_domain, get_repeat_record_count
from custom.enikshay.integrations.utils import is_valid_episode_submission

domain = 'enikshay'


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('old_repeater_id')
        parser.add_argument('new_repeater_id')

    def handle(self, old_repeater_id, new_repeater_id, **options):
        new_repeater = Repeater.get(new_repeater_id)

        records = iter_repeat_records_by_domain(domain, repeater_id=old_repeater_id)
        record_count = get_repeat_record_count(domain, repeater_id=old_repeater_id)
        accessor = CaseAccessors(domain)

        for record in with_progress_bar(records, length=record_count):

            try:
                episode = accessor.get_case(record.payload_id)
            except CaseNotFound:
                continue

            episode_case_properties = episode.dynamic_case_properties()
            if(episode_case_properties.get('private_nikshay_registered', 'false') == 'false'
               and not episode_case_properties.get('nikshay_id')
               and episode_case_properties.get('episode_type') == 'confirmed_tb'
               and is_valid_episode_submission(episode)):

                new_record = RepeatRecord(
                    domain=domain,
                    next_check=datetime.utcnow(),
                    repeater_id=new_repeater_id,
                    repeater_type=new_repeater.doc_type,
                    payload_id=record.payload_id,
                )
                new_record.save()

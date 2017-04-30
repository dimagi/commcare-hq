from django.core.management import BaseCommand

from custom.enikshay.private_sector_datamigration.models import LookupMaster


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--state_id',
            dest='state_id',
        )
        parser.add_argument(
            '--district_id',
            dest='district_id',
        )
        parser.add_argument(
            '--block_id',
            dest='block_id',
        )
        parser.add_argument(
            '--ward_id',
            dest='ward_id',
        )

    def handle(self, state_id=None, district_id=None, block_id=None, ward_id=None, **options):
        print ','.join([
            'state id',
            'district id',
            'block id',
            'ward id',
            'state name',
            'district name',
            'block name',
            'ward name',
        ])

        def _quote(string):
            return '"' + string + '"'

        states = LookupMaster.get_states()
        if state_id:
            states = [states.get(lookupKey=state_id)]

        for state in states:
            districts = LookupMaster.get_districts_by_state(state)
            if district_id:
                districts = [districts.get(lookupKey=district_id)]

            for district in districts:
                blocks = LookupMaster.get_blocks_by_district(district)
                if block_id:
                    blocks = [blocks.get(lookupKey=block_id)]

                for block in blocks:
                    wards = LookupMaster.get_wards_by_block(block)
                    if ward_id:
                        wards = [wards.get(lookupKey=ward_id)]

                    for ward in wards:
                        print ','.join([
                            state.lookupKey,
                            district.lookupKey,
                            block.lookupKey,
                            ward.lookupKey,
                            _quote(state.value),
                            _quote(district.value),
                            _quote(block.value),
                            _quote(ward.value),
                        ])


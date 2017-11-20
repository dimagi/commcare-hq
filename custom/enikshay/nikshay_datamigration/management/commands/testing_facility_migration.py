from __future__ import absolute_import
from __future__ import print_function
from django.core.management import BaseCommand

from dimagi.utils.decorators.memoized import memoized

from casexml.apps.case.mock import CaseFactory

from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.nikshay_datamigration.models import Followup


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_ids', nargs='*')

    def handle(self, domain, case_ids, **options):
        self.domain = domain
        self.missing_nikshay_codes = set()
        case_accessor = CaseAccessors(domain)

        if not case_ids:
            case_ids = case_accessor.get_case_ids_in_domain(type='test')

        for case_id in case_ids:
            test_case = case_accessor.get_case(case_id)
            case_properties = test_case.dynamic_case_properties()
            if self.should_update(case_properties):
                self.update_case(case_id, case_properties)
                print(case_id)
        print(self.missing_nikshay_codes)

    @staticmethod
    def should_update(case_properties):
        return (
            case_properties.get('migration_created_case') == 'true' and
            case_properties.get('migration_created_from_id') and
            'testing_facility_name' not in case_properties
        )

    def update_case(self, case_id, case_properties):
        followup_id = int(case_properties['migration_created_from_id'])
        followup = Followup.objects.get(id=followup_id)
        try:
            nikshay_codes = (
                followup.DmcStoCode,
                followup.DmcDtoCode,
                followup.DmcTbuCode,
                str(followup.DMC),
            )
            dmc = self._loc_code_to_location()[nikshay_codes]
        except KeyError:
            self.missing_nikshay_codes.add(nikshay_codes)
            return

        CaseFactory(self.domain).update_case(
            case_id,
            update={
                'testing_facility_id': dmc.location_id,
                'testing_facility_name': dmc.name,

                'legacy_DmcStoCode': followup.DmcStoCode,
                'legacy_DmcDtoCode': followup.DmcDtoCode,
                'legacy_DmcTbuCode': followup.DmcTbuCode,
                'legacy_DMC': followup.DMC,
            },
        )

    @memoized
    def _loc_code_to_location(self):
        def _get_key(dmc):
            def _get_nikshay_code(loc):
                return loc.metadata['nikshay_code']
            tu = dmc.parent
            dto = tu.parent
            cto = dto.parent
            sto = cto.parent
            return tuple(map(_get_nikshay_code, [sto, dto, tu, dmc]))

        all_dmc = SQLLocation.active_objects.filter(
            domain=self.domain,
            location_type__code='dmc'
        )
        return {
            _get_key(dmc_loc): dmc_loc
            for dmc_loc in all_dmc
        }

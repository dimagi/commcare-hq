from django.core.management import BaseCommand
from django.db.models import Q

from custom.enikshay.nikshay_datamigration.factory import get_nikshay_codes_to_location
from custom.enikshay.private_sector_datamigration.models import IdsToDto, Agency


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('agency_type')
        parser.add_argument(
            '--location-codes',
            dest='location_codes',
            default=None,
            nargs='*',
        )

    def handle(self, domain, agency_type, location_codes=None, **options):
        print ','.join([
            'location_id',
            'site_code',
            'name',
            'parent_site_code',
            'latitude',
            'longitude',
            'external_id',
            'Delete(Y/N)',
            'data: enikshay_enabled',
            'data: is_test',
            'data: nikshay_code',
            'data: private_sector_org_id',
            'data: tests_available',
        ])

        nikshay_codes_to_location = get_nikshay_codes_to_location(domain)

        dtos = IdsToDto.objects.all()
        if location_codes is not None:
            q = Q()
            for location_code in location_codes:
                q = q | Q(nikshay_location_code__startswith=location_code)
            dtos = dtos.filter(q)

        for dto in dtos:
            dto_location = nikshay_codes_to_location[dto.nikshay_location_code]
            for agency in Agency.get_agencies_by_ward(
                dto.state_id, dto.district_id, dto.block_id, dto.ward_id
            ).filter(
                agencyTypeId=agency_type,
            ):
                print ','.join([
                    '',
                    agency.nikshayId or '', # TODO - confirm value of agency site_code
                    agency.name or '',
                    dto_location.site_code,
                    '',
                    '',
                    '',
                    '',
                    'yes',
                    'no',
                    agency.nikshayId or '',
                    agency.organisationId or '',
                    ''
                ])


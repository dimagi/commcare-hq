import csv

from django.core.management import BaseCommand

from custom.enikshay.private_sector_datamigration.management.commands.create_cases_by_beneficiary import \
    get_beneficiaries


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--owner-state-id',
        )
        parser.add_argument(
            '--owner-district-id',
        )
        parser.add_argument(
            '--owner-organisation-ids',
            default=None,
            metavar='owner_organisation_id',
            nargs='+',
        )

        parser.add_argument(
            '--owner-suborganisation-ids',
            default=None,
            metavar='owner_suborganisation_id',
            nargs='+',
        )

    def handle(self, *args, **options):
        owner_district_id = options['owner_district_id']
        owner_organisation_ids = options['owner_organisation_ids']
        owner_suborganisation_ids = options['owner_suborganisation_ids']
        owner_state_id = options['owner_state_id']

        agency_to_beneficiary_count = {}
        agency_to_occurrence_count = {}
        agency_to_episode_count = {}
        agency_to_prescription_count = {}
        agency_to_adherence_count = {}

        for i, beneficiary in enumerate(get_beneficiaries(
            0, None, None, owner_state_id, owner_district_id,
            owner_organisation_ids, owner_suborganisation_ids
        )):
            if beneficiary._agency:
                agency_id = beneficiary._agency.agencyId

                agency_to_beneficiary_count[agency_id] = agency_to_beneficiary_count.get(agency_id, 0) + 1
                agency_to_occurrence_count[agency_id] = agency_to_occurrence_count.get(agency_id, 0) + 1
                agency_to_episode_count[agency_id] = agency_to_episode_count.get(agency_id, 0) + 1
                agency_to_prescription_count[agency_id] = agency_to_prescription_count.get(agency_id, 0) + beneficiary._prescription_count
                agency_to_adherence_count[agency_id] = agency_to_adherence_count.get(agency_id, 0) + beneficiary._adherence_count

            print 'done %d' % i

        with open('case_count_by_agency.csv', 'w') as output:
            csvwriter = csv.writer(output)

            csvwriter.writerow([
                'Agency ID',
                'person case count',
                'occurrence case count',
                'episode case count',
                'prescription case count',
                'adherence case count',
                'total case count',
            ])

            for agency_id in agency_to_beneficiary_count:
                case_counts = [
                    agency_to_beneficiary_count[agency_id],
                    agency_to_occurrence_count[agency_id],
                    agency_to_episode_count[agency_id],
                    agency_to_prescription_count[agency_id],
                    agency_to_adherence_count[agency_id],
                ]
                csvwriter.writerow(map(
                    str,
                    [agency_id] + case_counts + [sum(case_counts)]
                ))

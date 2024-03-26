import csv
import logging
from datetime import datetime

from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked

from corehq.apps.es.case_search import CaseSearchES, case_property_missing
from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.models.cases import CommCareCase
from corehq.util.log import with_progress_bar

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = 'Migrate location data from forms to cases'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('domain')
        parser.add_argument(
            'case_type',
            help="Case type on the domain to migrate for"
        )
        parser.add_argument(
            'case_property',
            help="Case property of case to save location data on"
        )
        parser.add_argument(
            'form_xmlns',
            help="XMLNS of the form that created/updated the case and has the location metadata"
        )

        parser.add_argument(
            '--include_closed_cases',
            action='store_true',
            default=False,
            help="Include closed cases in the migration",
        )

        parser.add_argument(
            '--dry_run',
            action='store_true',
            default=False,
            help="A dry run to only share the updates that would happen",
        )

    def handle(self, domain, case_type, case_property, form_xmlns, **options):
        include_closed_cases = options['include_closed_cases']
        dry_run = options['dry_run']

        cases_with_missing_case_property = (
            CaseSearchES().domain(domain).case_type(case_type)
            .filter(case_property_missing(case_property))
        )
        if not include_closed_cases:
            logger.info("Skipping closed cases. Use --include_closed_cases to include them as well")
            cases_with_missing_case_property = cases_with_missing_case_property.is_closed(False)

        case_ids = cases_with_missing_case_property.get_ids()
        number_of_cases_to_be_updated = len(case_ids)

        logger.info(f"Number of cases to be updated: {number_of_cases_to_be_updated}")

        if number_of_cases_to_be_updated == 0:
            logger.info("No cases to be updated. Bye!")
            return

        if dry_run:
            logger.warning("This is a dry run. Only expected updates with be shared and no cases will be updated.")
        else:
            logger.warning("THIS IS A REAL RUN. Cases will be updated.")

        confirmation = input("Please confirm if you would like to proceed?(y/n)")
        if confirmation == 'y':
            self._iterate_cases(domain, case_type, case_ids, form_xmlns, case_property, dry_run)
        else:
            logger.info("Aborted! No cases were updated.")

    def _iterate_cases(self, domain, case_type, case_ids, form_xmlns, case_property, dry_run):
        filename = "migrate_form_location_data_to_cases__%s_%s_%s.csv" % (
            domain, case_type, datetime.utcnow()
        )
        with open(filename, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, ['case_id', 'case_property_value'])
            writer.writeheader()
            for case_ids in chunked(with_progress_bar(case_ids), 100, list):
                case_updates = []

                cases = CommCareCase.objects.get_cases(case_ids, domain)
                for case in cases:
                    case_property_value = self._get_location_update_for_case(case, form_xmlns)
                    case_updates.append((case.case_id, {f'{case_property}': case_property_value}, False))
                    writer.writerow({'case_id': case.case_id, 'case_property_value': case_property_value})

                if not dry_run:
                    if case_updates:
                        logger.info(f"Updating {len(case_updates)} cases")
                        bulk_update_cases(domain, case_updates, device_id=__name__)
                        logger.info("Updated")

    def _get_location_update_for_case(self, case, form_xmlns):
        forms_with_location_data = self._get_relevant_forms_for_case(case, form_xmlns)

        if not forms_with_location_data:
            logger.warning(f"Could not find location data for case {case.case_id}")

        if forms_with_location_data:
            if len(forms_with_location_data) > 1:
                logger.warning("More than one matching forms for case. Picking the latest one")
                forms_with_location_data.sort(key=lambda _form: _form.received_on, reverse=True)
            location = forms_with_location_data[0].metadata.location
            return f"{location.latitude} {location.longitude} {location.altitude} {location.accuracy}"

    @staticmethod
    def _get_relevant_forms_for_case(case, form_xmlns):
        xform_ids = case.xform_ids
        forms = XFormInstance.objects.get_forms(xform_ids)
        forms_with_location_data = []
        for form in forms:
            if form.xmlns == form_xmlns:
                try:
                    if form.metadata.location:
                        forms_with_location_data.append(form)
                    else:
                        logger.info(f"Could not find location data on form {form.form_id}")
                except Exception as e:
                    logger.error(f"Error fetching location data on form {form.form_id}: {e}")
        return forms_with_location_data

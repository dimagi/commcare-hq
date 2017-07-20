"""
eNikshay 2B - Release 1 Migration
https://docs.google.com/spreadsheets/d/1GFpMht-C-0cMCQu8rfqQG9lgW9omfYi3y2nUXHR8Pio/edit#gid=0
"""
import datetime
import logging
from django.core.management import BaseCommand
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import CASE_TYPE_PERSON
from custom.enikshay.const import ENROLLED_IN_PRIVATE, CASE_VERSION

logger = logging.getLogger('two_b_datamigration')


def confirm(msg):
    if raw_input(msg + "\n(y/n)") != 'y':
        sys.exit()


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            help="The domain to migrate."
        )
        parser.add_argument(
            'dto_id',
            help="The id of the dto location to migrate."
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            help="actually create the cases. Without this flag, it's a dry run."
        )

    def handle(self, domain, dto_id, **options):
        commit = options['commit']
        logger.info("Starting {} migration on {} at {}".format(
            "real" if commit else "fake", domain, datetime.datetime.utcnow()
        ))
        dto = SQLLocation.objects.get(
            domain=domain, location_id=dto_id, location_type__code='dto')
        num_descendants = dto.get_descendants(include_self=True).count()
        confirm("Do you want to migrate the DTO '{}', which has {} descendants?"
                .format(dto.get_path_display(), num_descendants))
        migrator = ENikshay2BMigrator(domain, dto, commit)


class ENikshay2BMigrator(object):
    def __init__(self, domain, dto, commit):
        self.domain = domain
        self.dto = dto
        self.commit = commit
        self.accessor = CaseAccessors(self.domain)

    def migrate(self):
        persons = self.get_relevant_person_cases()
        for person in persons:
            self.migrate_person_case(person)

    def get_relevant_person_cases(self):
        # enrolled_in_private is blank/not set AND case_version is blank/not set
        # AND owner_id is within the location set being migrated
        location_owners = self.dto.get_descendants(include_self=True).location_ids()
        person_ids = self.accessor.get_open_case_ids_in_domain_by_type(CASE_TYPE_PERSON, location_owners)
        for person in self.accessor.iter_cases(person_ids):
            if (person.get_case_property(ENROLLED_IN_PRIVATE) != 'true'
                    and not person.get_case_property(CASE_VERSION)):
                yield person

    def migrate_person_case(self, person):
        pass

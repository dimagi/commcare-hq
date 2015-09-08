from optparse import make_option
from django.core.management.base import BaseCommand
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.apps.tzmigration.timezonemigration import prepare_planning_db, \
    get_planning_db, get_planning_db_filepath, delete_planning_db, \
    prepare_case_json, FormJsonDiff
from corehq.util.dates import iso_string_to_datetime
from couchforms.dbaccessors import get_form_ids_by_type


def _is_datetime(string):
    if not isinstance(string, basestring):
        return False
    try:
        iso_string_to_datetime(string)
    except (ValueError, OverflowError, TypeError):
        return False
    else:
        return True


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--prepare', action='store_true', default=False),
        make_option('--prepare-case-json', action='store_true', default=False),
        make_option('--blow-away', action='store_true', default=False),
        make_option('--stats', action='store_true', default=False),
        make_option('--show-diffs', action='store_true', default=False),
        make_option('--play', action='store_true', default=False),
    )

    def handle(self, domain, **options):
        filepath = get_planning_db_filepath(domain)
        self.stdout.write('Using file {}\n'.format(filepath))
        if options['blow_away']:
            delete_planning_db(domain)
            self.stdout.write('Removed file {}\n'.format(filepath))
        if options['prepare']:
            self.planning_db = prepare_planning_db(domain)
            self.stdout.write('Created and loaded file {}\n'.format(filepath))
        else:
            self.planning_db = get_planning_db(domain)
        if options['prepare_case_json']:
            prepare_case_json(self.planning_db)
        if options['stats']:
            self.valiate_forms_and_cases(domain)
        if options['show_diffs']:
            self.show_diffs()
        if options['play']:
            from corehq.apps.tzmigration.planning import *
            session = self.planning_db.Session()  # noqa
            try:
                import ipdb as pdb
            except ImportError:
                import pdb

            pdb.set_trace()

    def valiate_forms_and_cases(self, domain):
        form_ids_in_couch = set(get_form_ids_by_type(domain, 'XFormInstance'))
        form_ids_in_sqlite = set(self.planning_db.get_all_form_ids())

        print 'Forms in Couch: {}'.format(len(form_ids_in_couch))
        print 'Forms in Sqlite: {}'.format(len(form_ids_in_sqlite))
        if form_ids_in_couch ^ form_ids_in_sqlite:
            print 'In Couch only: {}'.format(
                list(form_ids_in_couch - form_ids_in_sqlite))

        case_ids_in_couch = set(get_case_ids_in_domain(domain))
        case_ids_in_sqlite = set(self.planning_db.get_all_case_ids())

        print 'Cases in Couch: {}'.format(len(case_ids_in_couch))
        print 'Cases in Sqlite: {}'.format(len(case_ids_in_sqlite))
        if case_ids_in_couch ^ case_ids_in_sqlite:
            print 'In Couch only: {}'.format(
                list(case_ids_in_couch - case_ids_in_sqlite))
            print 'In Sqlite only: {}'.format(
                list(case_ids_in_sqlite - case_ids_in_couch))

    def show_diffs(self):
        for form_id, json_diff in self.planning_db.get_diffs():
            if json_diff.diff_type == 'diff':
                if _is_datetime(json_diff.old_value) and _is_datetime(json_diff.new_value):
                    continue
            if json_diff in (
                    FormJsonDiff(diff_type=u'type', path=[u'external_id'], old_value=u'', new_value=None),
                    FormJsonDiff(diff_type=u'type', path=[u'closed_by'], old_value=u'', new_value=None)):
                continue
            print '[{}] {}'.format(form_id, json_diff)

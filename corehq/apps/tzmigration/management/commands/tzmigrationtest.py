from optparse import make_option
from django.core.management.base import BaseCommand
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.apps.tzmigration.timezonemigration import prepare_planning_db, \
    get_planning_db, get_planning_db_filepath, delete_planning_db
from corehq.util.dates import iso_string_to_datetime
from couchforms.dbaccessors import get_form_ids_by_type


def _is_datetime(string):
    if not isinstance(string, basestring):
        return False
    try:
        iso_string_to_datetime(string)
    except ValueError:
        return False
    else:
        return True


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--prepare', action='store_true', default=False),
        make_option('--blow-away', action='store_true', default=False),
        make_option('--stats', action='store_true', default=False),
        make_option('--show-diffs', action='store_true', default=False),
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
        if options['stats']:
            self.valiate_forms_and_cases(domain)
        if options['show_diffs']:
            self.show_diffs()
        if False:
            self.group_forms_and_cases()

    def group_forms_and_cases(self):
        all_form_ids = self.planning_db.get_all_form_ids()
        all_case_ids = self.planning_db.get_all_case_ids()
        groups = []
        i = 0
        while all_form_ids:
            i += 1
            form_id = all_form_ids.pop()
            form_ids, case_ids = self.planning_db.span_form_id(form_id)
            all_form_ids -= form_ids
            all_case_ids -= case_ids
            groups.append((form_ids, case_ids))

            print 'Group {}'.format(i)
            print 'Forms ({}): {}'.format(len(form_ids), form_ids)
            print 'Cases ({}): {}'.format(len(case_ids), case_ids)
        print "Left over cases: {}".format(all_case_ids)

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
        for form_id, json_diff in self.planning_db.get_form_diffs():
            if json_diff.diff_type == 'diff':
                if _is_datetime(json_diff.old_value) and _is_datetime(json_diff.new_value):
                    continue
            print '[{}] {}'.format(form_id, json_diff)

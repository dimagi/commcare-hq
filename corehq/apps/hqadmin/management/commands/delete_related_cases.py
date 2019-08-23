import csv342 as csv
from django.core.management import BaseCommand
import sys
from corehq.apps.receiverwrapper.util import get_app_version_info
from corehq.apps.users.util import cached_owner_id_to_display
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from six.moves import input
import six
from io import open


class Command(BaseCommand):
    help = "Delete all cases that are in a specific case's network/footprint"

    def add_arguments(self, parser):
        parser.add_argument('domain', type=six.text_type)
        parser.add_argument('case_id', type=six.text_type)
        parser.add_argument('--filename', dest='filename', default='case-delete-info.csv')

    def handle(self, domain, case_id, **options):
        case_accessor = CaseAccessors(domain=domain)
        case = case_accessor.get_case(case_id)
        if not case.is_deleted and input('\n'.join([
            'Case {} is not already deleted. Are you sure you want to delete it? (y/N)'.format(case_id)
        ])).lower() != 'y':
            sys.exit(0)
        dependent_case_ids = get_entire_case_network(domain, [case_id])

        cases_to_delete = [case for case in case_accessor.get_cases(dependent_case_ids) if not case.is_deleted]
        if cases_to_delete:
            with open(options['filename'], 'w') as csvfile:
                writer = csv.writer(csvfile)
                headers = [
                    'case id',
                    'case type',
                    'owner',
                    'opened by',
                    'app version',
                ]
                writer.writerow(headers)
                print(headers)

                for case in cases_to_delete:
                    form = FormAccessors(domain=domain).get_form(case.xform_ids[0])
                    app_version_info = get_app_version_info(
                        domain,
                        form.build_id,
                        form.form_data['@version'],
                        form.metadata,
                    )
                    row = [
                        case.case_id,
                        case.type,
                        cached_owner_id_to_display(case.owner_id) or case.owner_id,
                        cached_owner_id_to_display(case.opened_by),
                        app_version_info.build_version,
                    ]
                    writer.writerow(row)
                    print(row)

        if cases_to_delete and input('\n'.join([
            'Delete these {} cases? (y/N)'.format(len(cases_to_delete)),
        ])).lower() == 'y':
            case_accessor.soft_delete_cases([c.case_id for c in cases_to_delete])
            print('deleted {} cases'.format(len(cases_to_delete)))

        if cases_to_delete:
            print('details here: {}'.format(options['filename']))
        else:
            print("didn't find any cases to delete")


def get_entire_case_network(domain, case_ids):
    """
    Gets the entire network of case ids that depend on a passed in list of case ids.

    This includes all cases that index into the passed in cases (extensions or children)
    as well as all cases that index into those, recursively.
    """
    case_accessor = CaseAccessors(domain=domain)
    all_ids = set(case_ids)
    remaining_ids = set(case_ids)
    while remaining_ids:
        this_round_ids = set(c.case_id for c in case_accessor.get_reverse_indexed_cases(list(remaining_ids)))
        remaining_ids = this_round_ids - all_ids
        all_ids = all_ids | this_round_ids
    return all_ids

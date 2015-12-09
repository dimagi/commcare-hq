from optparse import make_option

from django.core.management import BaseCommand

from corehq.apps.app_manager.models import Application
from corehq.apps.hqcase.dbaccessors import get_number_of_cases_in_domain
from dimagi.utils.couch.database import iter_docs


def forms_with_empty_case_block(build):
    """
    Forms that may have caused this bug: http://manage.dimagi.com/default.asp?158371
    """
    try:
        app = Application.wrap(build)
    except:
        return

    forms = set()
    case_types = set()
    for module in app.get_modules():
        for form in module.get_forms():
            if form.requires == "case":
                if form.form_type == 'module_form' and not form.actions.update_case.update:
                    forms.add(form.xmlns)
                    case_types.add(module.case_type)
                elif form.form_type == 'advanced_form':
                    for action in form.actions.load_update_cases:
                        if not action.case_properties:
                            forms.add(form.xmlns)
                            case_types.add(action.case_type)

    return (case_types, forms) if forms or case_types else None


class Command(BaseCommand):
    help = ("Print a domains with case types and case counts that may be "
            "affected by http://manage.dimagi.com/default.asp?158371")
    option_list = BaseCommand.option_list + (
        make_option('--start',
                    action='store',
                    dest='startdate',
                    default='',
                    help='Start date'),
        make_option('--end',
                    action='store',
                    dest='enddate',
                    default='',
                    help='End date'),
    )

    def handle(self, *args, **options):
        start = options['startdate']
        end = options['enddate']

        print 'Starting...\n'
        ids = get_build_ids(start, end)

        print 'Checking {} builds\n'.format(len(ids))
        case_types_by_domain = {}
        all_form_xmlns = set()
        for build in iter_docs(Application.get_db(), ids):
            domain = build.get('domain')
            errors = forms_with_empty_case_block(build)
            if not errors:
                continue

            case_types, form_xmlns = errors
            all_form_xmlns |= form_xmlns
            domain_case_counts = case_types_by_domain.setdefault(domain, {})
            case_counts = {
                case_type: get_number_of_cases_in_domain(domain, case_type)
                for case_type in case_types
                if case_type not in domain_case_counts
            }
            domain_case_counts.update(case_counts)

        import pprint
        pprint.pprint(case_types_by_domain)

        print

        print all_form_xmlns


def get_build_ids(start, end):
    builds_ids = Application.view(
        'app_manager/builds_by_date',
        startkey=start,
        endkey=end,
        reduce=False,
        wrapper=lambda row: row['id']
    ).all()
    return builds_ids

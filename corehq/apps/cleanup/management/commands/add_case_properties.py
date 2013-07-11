from dimagi.utils.couch.database import get_db
from django.core.management import BaseCommand
from corehq.apps.domain.models import Domain
from dimagi.utils.chunked import chunked


def add_to_case(case):
    forms = {}
    def xforms(xid):
        xform = forms.get(xid)
        if not xform:
            xform = get_db().get(xid)
            forms[xid] = xform
        return xform

    should_save = False

    def get_user_id(form_id):
        return xforms(form_id).get('form', {}).get("case", {}).get("@user_id")

    for action in case.get('actions', []):
        if 'user_id' not in action:
            user_id = get_user_id(action.get('xform_id'))
            if user_id:
                action['user_id'] = user_id
                should_save = True

        if 'opened_by' not in case and action.get('action_type') == 'create':
            opened_by = get_user_id(action.get('xform_id'))
            if opened_by:
                case['opened_by'] = opened_by
                should_save = True

        if case.get('closed', False) and 'closed_by' not in case and action.get('action_type') == 'close':
            closed_by = get_user_id(action.get('xform_id'))
            if closed_by:
                case['closed_by'] = closed_by
                should_save = True

    return should_save

class Command(BaseCommand):
    args = '<domain_name domain_name ...>'
    help = """
        Loops through every case and adds the opened_by and closed_by property to each case where applicable.
        It also adds user_id to each case action in order to fix a bug.
    """

    def handle(self, *args, **options):
        domain_names = args or [d["key"] for d in Domain.get_all(include_docs=False)]
        for d in domain_names:
            print "Migrating cases in project space: %s" % d
            key = ["all", d]
            results = get_db().view('case/all_cases',
                startkey=key,
                endkey=key + [{}],
                reduce=False,
                include_docs=True,
            )
            for cases in chunked([r['doc'] for r in results], 100):
                cases_to_save = []
                for case in cases:
                    if add_to_case(case):
                        cases_to_save.append(case)
                get_db().bulk_save(cases_to_save)

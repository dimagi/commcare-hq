from casexml.apps.case.models import CommCareCase
from dimagi.utils.couch.database import get_db, iter_docs
from django.core.management import BaseCommand
from corehq.apps.domain.models import Domain

def add_to_case(case):
    forms = {}
    def get_xform(xid):
        xform = forms.get(xid)
        if not xform:
            xform = get_db().get(xid)
            forms[xid] = xform
        return xform

    should_save = False

    def get_user_id(form_id):
        if form_id:
            user_id = get_xform(form_id).get('form', {}).get("meta", {}).get("userID") or \
                get_xform(form_id).get('form', {}).get("case", {}).get("@user_id")
            if not user_id:
                print "Could not find a user_id for form %s" % form_id
            return user_id
            
        print "Case %s has actions without a proper xform_id" % case.get('_id')

    for action in case.get('actions', []):
        if not action.get('user_id'):
            user_id = get_user_id(action.get('xform_id'))
            if user_id:
                action['user_id'] = user_id
                should_save = True

        if not case.get('opened_by') and action.get('action_type') == 'create':
            opened_by = get_user_id(action.get('xform_id'))
            if opened_by:
                case['opened_by'] = opened_by
                should_save = True

        if case.get('closed', False) and not case.get('closed_by') and action.get('action_type') == 'close':
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
                include_docs=False,
            ).all()

            cases_to_save = []
            for i, raw_case in enumerate(iter_docs(CommCareCase.get_db(), [r['id'] for r in results])):
                if add_to_case(raw_case):
                    cases_to_save.append(raw_case)
                if i > 100:
                    get_db().bulk_save(cases_to_save)
                    cases_to_save = []
            get_db().bulk_save(cases_to_save)

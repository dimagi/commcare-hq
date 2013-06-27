from dimagi.utils.couch.database import get_db
from django.core.management import BaseCommand
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from couchforms.models import XFormInstance
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import wrapped_docs
from dimagi.utils.couch.database import iter_docs


def add_to_case(case):
    forms = {}
    def xforms(xid):
        xform = forms.get(xid)
        if not xform:
            xform = XFormInstance.get(xid)
            forms[xid] = xform
        return xform

    should_save = False

    for action in case.actions:
        if not action.user_id:
            user_id = xforms(action.xform_id)._form.get("case", {}).get("@user_id")
            if user_id:
                action.user_id = user_id
                should_save = True

        if not case.opened_by and action.action_type == 'create':
            opened_by = xforms(action.xform_id)._form.get("case", {}).get("@user_id")
            if opened_by:
                case.opened_by = opened_by
                should_save = True

        if case.closed and not case.closed_by and action.action_type == 'close':
            closed_by = xforms(action.xform_id)._form.get("case", {}).get("@user_id")
            if closed_by:
                case.closed_by = closed_by
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
            )
            for case_ids in chunked([r['id'] for r in results], 100):
                for case in wrapped_docs(CommCareCase, case_ids):
                    if add_to_case(case):
                        case.save()

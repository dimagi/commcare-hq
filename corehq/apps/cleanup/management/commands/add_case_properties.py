from django.core.management import BaseCommand
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs


def add_to_case(case):
    forms = {}
    def xforms(xid):
        xform = forms.get(xid)
        if not xform:
            xform = XFormInstance.get(xid)
            forms[xid] = xform
        return xform

    if not case.opened_by:
        creating_xform = xforms(case.xform_ids[0])
        case.opened_by = creating_xform.metadata.userID
    if case.closed and not case.closed_by:
        closing_xform = xforms(case.xform_ids[-1])
        case.closed_by = closing_xform.metadata.userID

    for action in case.actions:
        if not action.user_id:
            action.user_id = xforms(action.xform_id).metadata.userID

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
            for case in CommCareCase.by_domain(d):
                add_to_case(case)
                case.save()

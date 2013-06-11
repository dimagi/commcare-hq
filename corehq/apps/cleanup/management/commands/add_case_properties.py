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

    should_save = False

    for action in case.actions:
        if not action.user_id:
            action.user_id = xforms(action.xform_id).metadata.userID
            should_save = True

        if not case.opened_by and action.action_type == 'create':
            case.opened_by = xforms(action.xform_id).metadata.userID
            should_save = True

        if case.closed and not case.closed_by and action.action_type == 'close':
            case.closed_by = xforms(action.xform_id).metadata.userID
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
            for case in CommCareCase.by_domain(d):
                if add_to_case(case):
                    case.save()

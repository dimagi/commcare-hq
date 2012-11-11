from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import WebUser
from pact.management.commands.constants import PACT_DOMAIN

def get_user_id_map():
    all_users = WebUser.by_domain(PACT_DOMAIN)
    old_id_map = {}
    for u in all_users:
        old_user_id = getattr(u, 'old_user_id', None)
        if old_user_id is not None:
            old_id_map[str(u['old_user_id'])] = u.get_id
    print old_id_map
    return old_id_map


def purge_case(case_id):
    """
    Delete a case based upon the case id
    """
    try:
        casedoc = CommCareCase.get(case_id)
    except Exception, ex:
        print "Case doesn't exist, we're done"
        return
    print "Purging case %s" % case_id

    db = CommCareCase.get_db()

    #purge all xforms found in that case
    xform_ids = casedoc.xform_ids
    for xform_id in xform_ids:
        if db.doc_exist(xform_id):
            db.delete_doc(xform_id)
            print "\tdeleted %s/%s" % (case_id, xform_id)
    db.delete_doc(casedoc)
    print "case purged"


def base_create_block(pact_id, case_id, user_id, name, type, owner_id):
    """
    Skeleton case to send to HQ
    """
    return """
    <case xmlns="http://commcarehq.org/case/transaction/v2" case_id="%(case_id)s" date_modified="2012-08-01" user_id="%(user_id)s">
        <create>
            <case_type>%(case_type)s</case_type>
            <case_name>%(case_name)s</case_name>
            <owner_id>%(owner_id)s</owner_id>
            <external_id>%(pact_id)s</external_id>
            <pactid>%(pact_id)s</pactid>
        </create>
    </case>
    """ % {
            "case_id": case_id,
            "user_id": user_id,
            "case_type": type,
            "case_name": name,
            "owner_id": owner_id,
            "pact_id": pact_id,
            }
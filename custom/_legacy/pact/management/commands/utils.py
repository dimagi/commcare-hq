from datetime import datetime
import uuid
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import WebUser, CommCareUser
from pact.enums import PACT_DOMAIN


def get_user_id_map():
    print "Retrieving migrated pact users from HQ and setting map"
    all_users = CommCareUser.by_domain(PACT_DOMAIN)
    old_id_map = {}
    for u in all_users:
        old_user_id = getattr(u, 'old_user_id', None)
        if old_user_id is not None:
            old_id_map[str(u['old_user_id'])] = u.get_id
    return old_id_map



def purge_case(case_id):
    """
    Delete a case based upon the case id
    """
    try:
        casedoc = CommCareCase.get(case_id)
    except Exception, ex:
        print "Case %s not found" % case_id
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

def make_meta_block(self, instance_id=None, timestart=None, timeend=None, webuser=None):
    if timestart is None:
        timestart = datetime.utcnow()
    if timeend is None:
        timeend = datetime.utcnow()

    if webuser is None:
        if CommCareUser.get_by_username('pactimporter@pact.commcarehq.org') is None:
            raise Exception("Pact importer user not created")
        webuser = CommCareUser.get_by_username('pactimporter@pact.commcarehq.org')

    if instance_id is None:
        instance_id = uuid.uuid4().hex

    meta_block = """
        <meta>
            <deviceID>pact_case_importer</deviceID>
            <timeStart>%(timestart)s</timeStart>
            <timeEnd>%(timeend)s</timeEnd>
            <username>%(username)s</username>
            <userID>%(userid)s</userID>
            <instanceID>%(instance_id)s</instanceID>
        </meta>""" % {
        "username": webuser.username,
        "userid": webuser.get_id,
        "timestart": timestart.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "timeend": timeend.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "instance_id": instance_id,
        }
    return meta_block

def base_create_block(pactid, case_id, user_id, name, type, owner_id, primary_hp, demographics):
    """
    Skeleton case to send to HQ
    """

    def make_demographics(demogs):
        yield "<update>"
        for k,v in demogs.items():
            if v != "" and v is not None:
                yield "<%(tag)s>%(val)s</%(tag)s>" % {'tag': k, 'val': v}
        yield "</update>"

    return """<case xmlns="http://commcarehq.org/case/transaction/v2" case_id="%(case_id)s" user_id="%(user_id)s">
        <create>
            <case_type>%(case_type)s</case_type>
            <case_name>%(case_name)s</case_name>
            <owner_id>%(owner_id)s</owner_id>
            <primary_hp>%(primary_hp)s</primary_hp>
            <external_id>%(pactid)s</external_id>
            <pactid>%(pactid)s</pactid>
        </create>
        %(demographics_block)s
    </case>
    """ % {
            "case_id": case_id,
            "user_id": user_id,
            "case_type": type,
            "case_name": name,
            "owner_id": owner_id,
            "pactid": pactid,
            "primary_hp": primary_hp,
            'demographics_block': ''.join(make_demographics(demographics))
            }



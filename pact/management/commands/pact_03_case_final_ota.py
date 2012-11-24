#OTA restore from pact
#recreate submissions to import as new cases to
from StringIO import StringIO
import pdb
import urllib2
from datetime import datetime
import uuid

from django.core.management.base import NoArgsCommand
from gunicorn.http import body
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests import CaseBlock
from corehq.apps.domain.models import Domain
import sys
import getpass
from lxml import etree
from corehq.apps.users.models import WebUser
from couchforms.util import post_xform_to_couch
from pact.management.commands import PactMigrateCommand
from pact.management.commands.utils import get_user_id_map
from pact.enums import PACT_DOMAIN


from receiver.util import spoof_submission

from gevent.pool import Pool
from gevent import monkey; monkey.patch_all()

from restkit.session import set_session
from restkit import Resource
set_session("gevent")

POOL_SIZE = 15

class Command(PactMigrateCommand):
    help = "OTA restore from pact server but ONLY create stub of cases"
    option_list = NoArgsCommand.option_list + (
    )

    def restore_by_network(self):
        username = raw_input("""\tEnter pact username: """)
        if username == "":
            return

        password = getpass.getpass("""\tEnter pact password: """)
        if password == "":
            return

        mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()

        pact_restore_url = 'https://pact.dimagi.com/restore'
        pact_realm = 'DJANGO'

        passwdmngr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        passwdmngr.add_password(pact_realm, pact_restore_url, username, password)
        authhandler = urllib2.HTTPDigestAuthHandler(passwdmngr)
        opener = urllib2.build_opener(authhandler)
        urllib2.install_opener(opener)

        try:
            req = urllib2.Request(pact_restore_url)
            #req.add_header('Content-Type', 'application/xml')
            res = urllib2.urlopen(req)
            #return res.read()
            fout = open('restore.xml', 'wb')
            payload = res.read()
            fout.write(payload)
            fout.close()
            return payload
        except urllib2.HTTPError, e:
            print e

    def cleanup_case(self, case_id):
        try:
            casedoc = CommCareCase.get(case_id)
        except Exception, ex:
            return
        print "cleaning up case %s" % case_id

        db = CommCareCase.get_db()
        xform_ids = casedoc.xform_ids

        for xform_id in xform_ids:
            if db.doc_exist(xform_id):
                db.delete_doc(xform_id)
                print "deleted: %s" % xform_id
        db.delete_doc(casedoc)
        print "\tcase deleted"



    def base_create_block(self, pact_id, case_id, user_id, name, type, owner_id):
        return """
        <case xmlns="http://commcarehq.org/case/transaction/v2" case_id="%(case_id)s" date_modified="2012-08-01" user_id="%(user_id)s">
            <create>
                <case_type>%(case_type)s</case_type>
                <case_name>%(case_name)s</case_name>
                <owner_id>%(owner_id)s</owner_id>
                <external_id>%(pact_id)s</external_id>
        </case>
        """ % {
            "case_id": case_id,
            "user_id": user_id,
            "case_type": type,
            "case_name": name,
            "owner_id": owner_id,
            "pact_id": pact_id,
        }





    def submit_case_block(self, caseblock):
        form = etree.Element("data", nsmap={None:  "http://www.commcarehq.org/pact/caseimport",
                                            'jrm':  "http://openrosa.org/jr/xforms" })
        instance_id = uuid.uuid4().hex
        meta_block = """<meta>
            <deviceID>pact_case_importer</deviceID>
            <timeStart>%(timestart)s</timeStart>
            <timeEnd>%(timeend)s</timeEnd>
            <username>dmyung@dimagi.com</username>
            <userID>dmyung@dimagi.com</userID>
            <instanceID>%(instanceid)s</instanceID>
        </meta>""" % {
            "timestart": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "timeend": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "instanceid": instance_id,
        }
        form.append(etree.XML(meta_block))
        form.append(caseblock)
        submission_xml_string = etree.tostring(form)
        p = Resource('http://localhost:8000')
        f = StringIO(submission_xml_string.encode('utf-8'))
        f.name = 'form.xml'
        res = p.post('/a/pact/receiver', payload= { 'xml_submission_file': f }, headers={'content-type':"multipart/form-data"})
        print res

    def handle(self, **options):
        domain_obj = Domain.get_by_name(PACT_DOMAIN)

#        payload = self.restore_by_network()
        with open('restore.xml', 'rb') as fin:
            payload = fin.read()
        tree = etree.fromstring(payload)
        old_id_map =get_user_id_map()

        def process_case(casexml_string):
            """
            Parse the latest casexml from pact to get the core info to make a stub case on hq
            """
            child = etree.fromstring(casexml_string)
            if child.tag != "{http://commcarehq.org/case/transaction/v2}case":
                return
            pdb.set_trace()
            remapped_user_id = old_id_map.get(child.get('user_id'), None)
            case_id = child.get('case_id')
            pact_id = child.get('update').get('pactid')
            type = child.get('create').get('case_type')
            name = child.get('create').get('case_name')

            self.cleanup_case(case_id)

            if remapped_user_id is not None:
                #print "Set remapped id: %s->%s" % (child.get('user_id'),  remapped_user.username)
                child.set('user_id', remapped_user_id._id)
#            self.submit_case_create_block(child)

        pool = Pool(POOL_SIZE)
        for child in tree.getchildren():
            xmlstr = etree.tostring(child)
            process_case(xmlstr)
#            pool.spawn(process_case, xmlstr)
#            if pool.full():
#                print "Pool full, waiting..."
#                pool.join()
#                print "Pool freed, continuing..."




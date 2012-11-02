#OTA restore from pact
#recreate submissions to import as new cases to
import pdb
import urllib2
from datetime import datetime
import uuid

from django.core.management.base import NoArgsCommand
from casexml.apps.case.tests import CaseBlock
from corehq.apps.domain.models import Domain
import sys
import getpass
from lxml import etree
from couchforms.util import post_xform_to_couch
from receiver.util import spoof_submission


class Command(NoArgsCommand):
    help = "OTA restore from pact server"
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
            return res.read()
            #fout = open('restore.xml', 'wb')
            #fout.write(res.read())
            #fout.close()
            #print res.read()


        except urllib2.HTTPError, e:
            print e

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


        #form.attrib['xmlns'] = "http://www.commcarehq.org/pact/caseimport"
        #form.attrib['xmlns:jrm'] = "http://openrosa.org/jr/xforms"

        form.append(etree.XML(meta_block))
        form.append(caseblock)

        #for block in case_blocks:
        #form.append(block)
        submission_xml_string = etree.tostring(form)
        #print submission_xml_string
        #print "#################################\nCase Update Submission: %s" % sender_name
        #print_pretty_xml(submission_xml_string)
        #print "#################################\n\n"
        #xform_posted = post_xform_to_couch(etree.tostring(form))
        #xform_posted = post_xform_to_couch(etree.tostring(form))
        xform_posted = spoof_submission('http://localhost:8000/a/pact/receiver',
            submission_xml_string,
            name="form.xml")
        #return xform_posted
        print "Submitted doc_id: %s" % instance_id
        print xform_posted

    def handle(self, **options):
        domain_obj = Domain.get_by_name('pact')

        #payload = self.restore_by_network()
        with open('restore.xml', 'rb') as fin:
            payload = fin.read()
        tree = etree.fromstring(payload)
        for child in tree.getchildren():
            #print etree.tostring(child)
            self.submit_case_block(child)




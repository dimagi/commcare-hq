#OTA restore from pact
#recreate submissions to import as new cases to
from StringIO import StringIO
from django.test.client import RequestFactory
import gevent
import simplejson
import urllib2
from datetime import datetime
import uuid

from django.core.management.base import NoArgsCommand
from corehq.apps.domain.models import Domain
import sys
import getpass
from lxml import etree
from corehq.apps.users.models import WebUser
from pact.management.commands import PactMigrateCommand
from pact.management.commands.constants import PACT_URL, POOL_SIZE
from pact.enums import PACT_DOMAIN, PACT_HP_GROUP_ID, PACT_CASE_TYPE
from pact.management.commands.utils import get_user_id_map, base_create_block, purge_case

from gevent.pool import Pool
from gevent import monkey
from receiver.signals import successful_form_received

monkey.patch_all()

from restkit.session import set_session

set_session("gevent")
from restkit import Resource


class Command(PactMigrateCommand):
    help = "OTA restore from pact server"
    option_list = NoArgsCommand.option_list + (
    )


    def get_meta_block(self, instance_id=None, timestart=None, timeend=None, webuser=None):
        if timestart is None:
            timestart = datetime.utcnow()
        if timeend is None:
            timeend = datetime.utcnow()

        if webuser is None:
            if WebUser.get_by_username('pactimporter') is None:
                raise Exception("Pact importer user not created")
            webuser = WebUser.get_by_username('pactimporter')

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

    def submit_case_create_block(self, opened_on, caseblock):
        form = etree.Element("data", nsmap={None: "http://www.commcarehq.org/pact/caseimport",
                                            'jrm': "http://openrosa.org/jr/xforms"})

        meta_block = self.get_meta_block(timestart=opened_on, timeend=opened_on)
        form.append(etree.XML(meta_block))
        form.append(etree.XML(caseblock))

        submission_xml_string = etree.tostring(form)
        self.submit_xform_rf(
            {
                'server_date': datetime.strftime(opened_on, "%Y-%m-%dT%H:%M:%SZ"),
                'date': datetime.strftime(opened_on, "%Y-%m-%dT%H:%M:%SZ"),
            },
            submission_xml_string)

    def disable_signals(self):
        print "Disabling signals"
        print len(successful_form_received.receivers)
        #disable signals:
        from casexml.apps.phone.signals import send_default_response

        successful_form_received.disconnect(send_default_response)

        from corehq.apps.app_manager.signals import get_custom_response_message

        successful_form_received.disconnect(get_custom_response_message)

        from corehq.apps.receiverwrapper.signals import create_case_repeat_records,\
            create_short_form_repeat_records, create_case_repeat_records, create_form_repeat_records

        from casexml.apps.case.signals import case_post_save

        successful_form_received.disconnect(create_form_repeat_records)
        successful_form_received.disconnect(create_short_form_repeat_records)
        case_post_save.disconnect(create_case_repeat_records)
        print "successful_form_received signals truncated: %d" % len(successful_form_received.receivers)

    def handle(self, **options):
        domain_obj = Domain.get_by_name(PACT_DOMAIN)
        self.old_id_map = get_user_id_map()
        print self.old_id_map
        self.get_credentials()
        self.disable_signals()


        #get cases
        case_ids = simplejson.loads(self.get_url(PACT_URL + 'hqmigration/cases/'))
        pool = Pool(POOL_SIZE)

        print "Purging All Cases"
        for id in case_ids:
#            purge_case(id)
            pool.spawn(purge_case, id)

        print "all cases pooled for purge"
        pool.join()
        print "Cases Purged"

        import random

        random.shuffle(case_ids)

        for id in case_ids:
            try:
                case_json = simplejson.loads(self.get_url(PACT_URL + 'hqmigration/cases/%s' % id))
            except Exception, ex:
                print "@@@@@@@@@@@@ Error on case %s" % id
                #hard exit because we need to make sure this never fails
                sys.exit()
            #            self.process_case(case_json)
            pool.spawn(self.process_case, case_json)
        pool.join()

    def process_xform_meta(self, action, xmlns, form_root ):
        tag_checks = {
            '{http://openrosa.org/jr/xforms}meta': #NEW META
                '{http://openrosa.org/jr/xforms}userID',
            '{%s}Meta' % xmlns: #OLD META
                '{%s}chw_id' % xmlns
        }

        def fix_meta(tag, node):
            userid_node = node.find(tag)
            userid = userid_node.text
            remapped_userid = self.old_id_map.get(userid, 'unknown')
            userid_node.text = remapped_userid

        metanode = None
        for meta, id_tag in tag_checks.items():
            #iterate through old vs. new meta blocks to find it
            metanode = form_root.find(meta)
            if metanode is not None:
                fix_meta(id_tag, metanode)
                break

        if metanode is None:
            #no meta because it's a hacked up form submission. reconstruct meta from the actions
            adate = datetime.strptime(action.get('date', None), '%Y-%m-%dT%H:%M:%SZ')
            mkmeta = self.get_meta_block(instance_id=action['xform_id'], timestart=adate, timeend=adate)
            form_root.append(etree.XML(mkmeta))
            #            print etree.tostring(xfroot, pretty_print=True)
    def fix_case(self, action, xmlns, form_root):
        #Walk the case tags to update the type if it was munged
        def walk_case_tags(taglist, subnode):
            case_node = subnode.find(taglist[0])
            if case_node is not None:
                update_node = case_node.find(taglist[1])
                if update_node is not None:
                    type_node = update_node.find(taglist[2])
                    if type_node is not None:
#                        print "Got type node!"
                        if type_node.text != PACT_CASE_TYPE:
                            orig_text = type_node.text
                            type_node.text = PACT_CASE_TYPE
                            update_node.append(etree.XML("<hp_status>%s</hp_status>" % orig_text))
#                            print etree.tostring(form_root, pretty_print=True)
                            return True
            return False



        new_casetags =  ['{http://commcarehq.org/case/transaction/v2}case',  '{http://commcarehq.org/case/transaction/v2}case', '{http://commcarehq.org/case/transaction/v2}update',]
        old_casetags = ['{%s}case' % xmlns, '{%s}update' % xmlns, '{%s}type' % xmlns ]

        for tags in [new_casetags, old_casetags]:
            if walk_case_tags(tags, form_root):
                break



    def process_xform_from_action(self, action):
        """
        Get xform from server and process it with new userid and submit it to hq
        """
        xform_xml = self.get_url(PACT_URL + "hqmigration/xform/%s/" % action['xform_id'])
        xfroot = etree.fromstring(xform_xml)

        nsmap = xfroot.nsmap
        xmlns = nsmap[None]

        self.process_xform_meta(action, xmlns, xfroot)
        self.fix_case(action, xmlns, xfroot)

        try:
            self.submit_xform_rf(action, etree.tostring(xfroot))
        except Exception, ex:
            print "\t\tError: %s: %s" % (action['xform_id'], ex)
            #        print "Form %s submitted" % action['xform_id']


    def process_case(self, case_json):
        print "############## Starting Case %s ##################" % case_json['_id']
        case_id = case_json['_id']
        pact_id = case_json['pactid']
        name = case_json['name']
        case_type = 'cc_path_client' # case_json['type']
        user_id = self.old_id_map.get(case_json['user_id'], None)
        owner_id = PACT_HP_GROUP_ID

        #make new blank case
        new_block = base_create_block(pact_id, case_id, user_id, name, case_type, owner_id, case_json['demographics'])

        opened_date = datetime.strptime(case_json['opened_on'], '%Y-%m-%dT%H:%M:%SZ')
        res = self.submit_case_create_block(opened_date, new_block)
        print "\tRegenerated case"

        for ix, action in enumerate(case_json['actions']):
            print "\t[%s] %s/%s (%d/%d)" % (
                pact_id, case_id, action['xform_id'], ix, len(case_json['actions']))
            self.process_xform_from_action(action)

        #todo: verify actions on migrated case
        print "########### Case %s completed ###################" % case_json['_id']







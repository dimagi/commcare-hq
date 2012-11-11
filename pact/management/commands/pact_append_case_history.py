#OTA restore from pact
#recreate submissions to import as new cases to
import pdb
import urllib2
from datetime import datetime
import uuid
import simplejson

from django.core.management.base import NoArgsCommand
from casexml.apps.case.tests import CaseBlock
from corehq.apps.domain.models import Domain
import sys
import getpass
from lxml import etree
from corehq.apps.users.models import WebUser
from couchforms.util import post_xform_to_couch
from pact.management.commands.constants import PACT_DOMAIN
from receiver.util import spoof_submission
from casexml.apps.case.models import CommCareCase
from couchdbkit.exceptions import ResourceNotFound


class Command(NoArgsCommand):
    help = "OTA restore from pact server"
    option_list = NoArgsCommand.option_list + (
    )

    def handle(self, **options):
        domain_obj = Domain.get_by_name(PACT_DOMAIN)

        with open('pact_raw_cases.json', 'rb') as fin:
            payload = fin.read()

        case_list_json = simplejson.loads(payload)
        for old_case_json in case_list_json:
            print "Backloading history: %s ..." % old_case_json['_id']
            try:
                curr_case = CommCareCase.get(old_case_json['_id'])
            except ResourceNotFound, ex:
                print "\tCase not found"
                continue
            old_case = CommCareCase.wrap(old_case_json)

            last_actions = curr_case['actions']
            last_xforms = curr_case['xform_ids']

            combined_actions = sorted(set(old_case['actions'] + last_actions), key=lambda x:x.date)
            curr_case['actions'] = combined_actions

            combined_raw_xforms = set(old_case['xform_ids'] + last_xforms)
            actions_xforms = set([x.xform_id for x in combined_actions])

            print "Actions/xform delta: %s" % (len(combined_raw_xforms.difference(actions_xforms)))
            curr_case['xform_ids'] = [x.xform_id for x in combined_actions]

            curr_case.save()
            print "Backloading history: %s done for %d actions" % (old_case_json['_id'], len(old_case_json['actions']))





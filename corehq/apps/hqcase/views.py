# stub views file
from collections import defaultdict
from copy import deepcopy
import json
import re
import uuid
import xml.etree.ElementTree as ET

from casexml.apps.case import const
from casexml.apps.phone.xml import get_case_xml
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from django.contrib import messages
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponse
from django.shortcuts import render

from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.decorators import login_and_domain_required, require_superuser
from corehq.apps.users.util import user_id_to_username

@login_and_domain_required
def open_cases_json(request, domain):
    delete_ids = json.loads(request.GET.get('delete_ids', 'false'))

    cases = CommCareCase.get_all_cases(domain, status='open', include_docs=True)

    user_id_to_type_to_cases = defaultdict(lambda:defaultdict(list))
    for case in cases:
        case_json = deepcopy(case.to_json())
        user_id_to_type_to_cases[case.user_id][case.type].append(case_json)
        del case_json['domain']

        if delete_ids:
            del case_json['_id']
            del case_json['_rev']
            del case_json['user_id']
#            del case_json['type']
            del case_json['doc_type']
            case_json['actions'] = [action.action_type for action in case.actions]
            case_json['referrals'] = [referral.type for referral in case.referrals]

    usercases = [{
        "username": user_id_to_username(user_id),
        "cases": [{"type": type, "cases":cases} for (type, cases) in type_to_cases.items()]
    } for (user_id, type_to_cases) in user_id_to_type_to_cases.items()]
    usercases.sort(key=lambda x: x['username'])
    return HttpResponse(json.dumps(usercases))

@login_and_domain_required
def open_cases(request, domain, template="hqcase/open_cases.html"):
    return render(request, template, {"domain": domain})

@require_superuser
def explode_cases(request, domain, template="hqcase/explode_cases.html"):
    if request.method == 'POST':
        user_id = request.POST['user_id']
        user = CommCareUser.get_by_user_id(user_id, domain)
        factor = request.POST.get('factor', '2')
        try:
            factor = int(factor)
        except ValueError:
            messages.error(request, 'factor must be an int; was: %s' % factor)
        else:
            keys = [[domain, owner_id, False] for owner_id in user.get_owner_ids()]
            for case in CommCareCase.view('hqcase/by_owner',
                keys=keys,
                include_docs=True,
                reduce=False
            ):
                # we'll be screwing with this guy, so make him unsaveable
                # case.save = None
                old_case_id = case._id
                for i in range(factor - 1):
                    case._id = uuid.uuid4().hex
                    case_block = get_case_xml(case, (const.CASE_ACTION_CREATE, const.CASE_ACTION_UPDATE), version='2.0')
                    case_block, attachments = process_case_block(case_block, case.case_attachments, old_case_id)
                    submit_case_blocks(case_block, domain, attachments=attachments)

            messages.success(request, "All of %s's cases were exploded by a factor of %d" % (user.raw_username, factor))

    return render(request, template, {
        'domain': domain,
        'users': CommCareUser.by_domain(domain),
    })

def process_case_block(case_block, attachments, old_case_id):
    def get_namespace(element):
        m = re.match('\{.*\}', element.tag)
        return m.group(0)[1:-1] if m else ''

    def local_attachment(attachment, old_case_id, tag):
        mime = attachment['server_mime']
        size = attachment['attachment_size']
        src = attachment['attachment_src']
        attachment_meta, attachment_stream = CommCareCase.fetch_case_attachment(old_case_id, tag)
        return UploadedFile(attachment_stream, src, size=size, content_type=mime)

    # Remove namespace because it makes looking up tags a pain
    root = ET.fromstring(case_block)
    xmlns = get_namespace(root)
    case_block = re.sub(' xmlns="[^"]+"', '', case_block, count=1)

    root = ET.fromstring(case_block)
    tag = "attachment"
    xml_attachments = root.find(tag)
    ret_attachments = {}

    if xml_attachments:
        for attach in xml_attachments:
            attach.attrib['from'] = 'local'
            attach.attrib['src'] = attachments[attach.tag]['attachment_src']
            ret_attachments[attach.attrib['src']] = local_attachment(attachments[attach.tag], old_case_id, attach.tag)

    # Add namespace back in without { } added by ET
    root.attrib['xmlns'] = xmlns
    return ET.tostring(root), ret_attachments

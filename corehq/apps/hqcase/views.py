# stub views file
from collections import defaultdict
from copy import deepcopy
import json
import uuid

from corehq.apps.hqcase.utils import submit_case_blocks, make_creating_casexml
from corehq.apps.users.models import CommCareUser
from django.contrib import messages
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponse
from django.shortcuts import render, redirect

from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.decorators import login_and_domain_required, require_superuser
from corehq.apps.users.util import user_id_to_username
from corehq.apps.hqcase.tasks import explode_case_task
from soil import DownloadBase

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
            del case_json['doc_type']
            case_json['actions'] = [action.action_type for action in case.actions]

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
            download = DownloadBase()
            res = explode_case_task.delay(user_id, domain, factor)
            download.set_task(res)

            return redirect('hq_soil_download', domain, download.download_id)

    return render(request, template, {
        'domain': domain,
        'users': CommCareUser.by_domain(domain),
    })

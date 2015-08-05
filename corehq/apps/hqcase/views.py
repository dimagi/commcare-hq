from corehq.apps.users.models import CommCareUser
from django.contrib import messages
from django.shortcuts import render, redirect

from corehq.apps.domain.decorators import require_superuser_or_developer
from corehq.apps.hqcase.tasks import explode_case_task
from soil import DownloadBase


@require_superuser_or_developer
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

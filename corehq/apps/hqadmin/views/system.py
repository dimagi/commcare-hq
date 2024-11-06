from collections import namedtuple

from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from corehq.apps.domain.decorators import (
    require_superuser,
    require_superuser_or_contractor,
)
from corehq.apps.domain.views.internal import get_project_limits_context
from corehq.apps.hqadmin import service_checks
from corehq.apps.hqadmin.service_checks import run_checks
from corehq.apps.hqadmin.views.utils import BaseAdminSectionView
from corehq.apps.receiverwrapper.rate_limiter import (
    global_submission_rate_limiter,
)


@require_superuser_or_contractor
def check_services(request):

    def get_message(service_name, result):
        if result.exception:
            status = "EXCEPTION"
            msg = repr(result.exception)
        else:
            status = "SUCCESS" if result.success else "FAILURE"
            msg = result.msg
        return "{} (Took {:6.2f}s) {:15}: {}<br/>".format(status, result.duration, service_name, msg)

    statuses = run_checks(list(service_checks.CHECKS))
    results = [
        get_message(name, status) for name, status in statuses
    ]
    return HttpResponse("<pre>" + "".join(results) + "</pre>")


@require_superuser
def branches_on_staging(request, template='hqadmin/branches_on_staging.html'):
    branches = _get_branches_merged_into_autostaging()
    branches_by_submodule = [(None, branches)] + [
        (cwd, _get_branches_merged_into_autostaging(cwd))
        for cwd in _get_submodules()
    ]
    return render(request, template, {
        'branches_by_submodule': branches_by_submodule,
    })


def _get_branches_merged_into_autostaging(cwd=None):
    import sh
    git = sh.git.bake(_tty_out=False, _cwd=cwd)
    # %p %s is parent hashes + subject of commit message, which will look like:
    # <merge base> <merge head> Merge <stuff> into autostaging
    try:
        pipe = git.log('origin/master...', grep='Merge .* into autostaging', format='%p %s')
    except sh.ErrorReturnCode_128:
        # when origin/master isn't fetched, you'll get
        #   fatal: ambiguous argument 'origin/master...': \
        #   unknown revision or path not in the working tree.
        git.fetch()
        return _get_branches_merged_into_autostaging(cwd=cwd)

    # sh returning string from command git.log(...)
    branches = pipe.strip().split("\n")
    CommitBranchPair = namedtuple('CommitBranchPair', ['commit', 'branch'])
    return sorted(
        (CommitBranchPair(
            *line.strip()
            .replace("Merge remote-tracking branch 'origin/", '')
            .replace("Merge branch '", '')
            .replace("' into autostaging", '')
            .split(' ')[1:]
        ) for line in branches),
        key=lambda pair: pair.branch
    )


def _get_submodules():
    """
    returns something like
    ['submodules/commcare-translations', 'submodules/django-digest-src', ...]
    """
    import sh
    git = sh.git.bake(_tty_out=False)
    submodules = git.submodule().strip().split("\n")
    return [
        line.strip()[1:].split()[1]
        for line in submodules
    ]


@method_decorator(require_superuser, name='dispatch')
class GlobalThresholds(BaseAdminSectionView):
    urlname = 'global_thresholds'
    page_title = gettext_lazy("Global Usage Thresholds")
    template_name = 'hqadmin/global_thresholds.html'

    @property
    def page_context(self):
        return get_project_limits_context([
            ('Submission Rate Limits', global_submission_rate_limiter),
        ])

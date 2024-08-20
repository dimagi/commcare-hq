from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from corehq import toggles
from corehq.apps.hqwebapp.decorators import use_bootstrap5


@login_required
@use_bootstrap5
@toggles.SAAS_PROTOTYPE.required_decorator()
def bootstrap5_amd_example(request):
    return render(request, 'prototype/webpack/bootstrap5_amd.html', {})


@login_required
@toggles.SAAS_PROTOTYPE.required_decorator()
def bootstrap3_amd_example(request):
    return render(request, 'prototype/webpack/bootstrap3_amd.html', {})


@login_required
@use_bootstrap5
@toggles.SAAS_PROTOTYPE.required_decorator()
def knockout_pagination(request):
    return render(request, 'prototype/webpack/knockout_pagination.html', {})

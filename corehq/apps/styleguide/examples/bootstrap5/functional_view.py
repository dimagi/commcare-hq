from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils.translation import gettext as _

from corehq.apps.domain.decorators import login_required
from corehq.apps.hqwebapp.context import get_page_context, Section, ParentPage
from corehq.apps.hqwebapp.decorators import use_bootstrap5


@require_POST  # often, other decorators will go here too
def example_data_view(request):  # any additional arguments from the URL go here
    # do something with the request data
    return JsonResponse({
        "success": True,
    })


def simple_redirect_view(request):
    # do something with the request
    return HttpResponseRedirect(reverse("example_centered_page_functional_b5"))  # redirect to a different page


@login_required
@use_bootstrap5
def example_centered_page_view(request):
    context = get_page_context(
        _("Centered Page Example"),
        reverse("example_centered_page_functional_b5"),
    )
    return render(request, 'styleguide/bootstrap5/examples/simple_centered_page.html', context)


@login_required  # often this is login_and_domain_required
@use_bootstrap5
def example_section_page_view(request):
    context = get_page_context(
        _("A Detail Page (Section Example)"),
        reverse("example_section_functional_b5"),
        section=Section(
            _("Example Views"),
            reverse("example_section_functional_b5"),
        ),
        parent_pages=[
            ParentPage(
                _("Section Page Example"),
                reverse("example_parent_page_functional_b5")
            ),
        ]
    )
    return render(request, 'styleguide/bootstrap5/examples/simple_section.html', context)


@login_required
@use_bootstrap5
def example_parent_page_view(request):
    context = get_page_context(
        _("Section Page Example"),
        reverse("example_parent_page_functional_b5"),
        section=Section(
            _("Example Views"),
            reverse("example_section_functional_b5"),
        ),
    )
    # this is not a standard template context variable
    context['child_page_url'] = reverse("example_section_functional_b5")
    return render(request, 'styleguide/bootstrap5/examples/simple_section_parent.html', context)

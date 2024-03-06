from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from corehq.apps.domain.decorators import login_required
from corehq.apps.hqwebapp.context import ParentPage
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView, BaseSectionPageView


@method_decorator(login_required, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class ExampleCenteredPageView(BasePageView):
    urlname = "example_centered_page_b5"
    page_title = gettext_lazy("Centered Page Example")
    template_name = "styleguide/bootstrap5/examples/simple_centered_page.html"

    @property
    def page_url(self):
        return reverse(self.urlname)


# Typically, section pages will all inherit from one "base section view" that
# defines the general page_url format, section_url, section_name, and the minimum
# required permissions decorators for that page.
@method_decorator(login_required, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class BaseExampleView(BaseSectionPageView):
    section_name = gettext_lazy("Example Views")

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def section_url(self):
        # This can be another page relevant to the section.
        # Since there are only two pages in this example section,
        # `ExampleParentSectionPageView.urlname` is used.
        return reverse(ExampleParentSectionPageView.urlname)


class ExampleParentSectionPageView(BaseExampleView):
    urlname = "example_section_parent_b5"
    page_title = gettext_lazy("Section Page Example")
    template_name = "styleguide/bootstrap5/examples/simple_section_parent.html"

    @property
    def page_context(self):
        return {
            "child_page_url": reverse(ExampleChildSectionPageView.urlname),
        }


class ExampleChildSectionPageView(BaseExampleView):
    urlname = "example_section_b5"
    page_title = gettext_lazy("A Detail Page (Section Example)")
    template_name = "styleguide/bootstrap5/examples/simple_section.html"

    @property
    def parent_pages(self):
        return [
            ParentPage(ExampleParentSectionPageView.page_title, reverse(ExampleParentSectionPageView.urlname)),
        ]

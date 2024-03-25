from django.urls import reverse
from django.utils.translation import gettext_lazy, gettext as _

from memoized import memoized

from corehq.apps.styleguide.examples.bootstrap5.class_view import (
    ExampleCenteredPageView,
    ExampleParentSectionPageView,
    ExampleChildSectionPageView,
)
from corehq.tabs.uitab import UITab
from corehq.tabs.utils import dropdown_dict


class StyleguideExamplesTab(UITab):
    title = gettext_lazy("Style Guide")
    view = 'example_centered_page_b5'

    url_prefix_formats = ('/styleguide/b5/example/',)

    @property
    def _is_viewable(self):
        examples_url = reverse("example_views_b5")
        return self.request_path.startswith(examples_url)

    @property
    def dropdown_items(self):
        submenu_context = [
            dropdown_dict(_("Class-Based Examples"), is_header=True),
            dropdown_dict(
                _("Basic Page"),
                url=reverse(ExampleCenteredPageView.urlname),
            ),
            dropdown_dict(
                _("Section Page"),
                url=reverse(ExampleChildSectionPageView.urlname),
            ),
            dropdown_dict(_("Functional Examples"), is_header=True),
            dropdown_dict(
                _("Basic Page"),
                url=reverse("example_centered_page_functional_b5"),
            ),
            dropdown_dict(
                _("Section Page"),
                url=reverse("example_section_functional_b5"),
            ),
            self.divider,
            dropdown_dict(
                _("Style Guide"),
                url=reverse("styleguide_home_b5"),
            ),
        ]
        return submenu_context

    @property
    @memoized
    def sidebar_items(self):
        return [
            (_("Class-Based Views"), [
                {
                    'title': ExampleCenteredPageView.page_title,
                    'url': reverse(ExampleCenteredPageView.urlname),
                },
                {
                    'title': ExampleParentSectionPageView.page_title,
                    'url': reverse(ExampleParentSectionPageView.urlname),
                    "subpages": [
                        {
                            'title': ExampleChildSectionPageView.page_title,
                            'urlname': ExampleChildSectionPageView.urlname,
                        },
                    ],
                },
            ]),
            (_("Functional Views"), [
                {
                    'title': _("Centered Page Example"),
                    'url': reverse("example_centered_page_functional_b5"),
                },
                {
                    'title': _("Section Page Example"),
                    'url': reverse("example_parent_page_functional_b5"),
                    "subpages": [
                        {
                            'title': _("A Detail Page (Section Example)"),
                            'urlname': "example_section_functional_b5",
                        },
                    ],
                },
            ]),
        ]

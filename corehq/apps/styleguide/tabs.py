from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from memoized import memoized

from corehq.apps.styleguide.examples.simple_crispy_form.views import (
    DefaultSimpleCrispyFormSectionView,
    SimpleCrispyFormView,
)
from corehq.apps.styleguide.views import (
    MainStyleGuideView,
    MoleculesStyleGuideView,
)
from corehq.apps.styleguide.views.docs import (
    FormsSimpleCrispyFormExampleView,
    ViewsSimpleCrispyFormExampleView,
)
from corehq.tabs.uitab import UITab
from corehq.tabs.utils import dropdown_dict


class BaseSGTab(UITab):

    @property
    def _is_viewable(self):
        docs_url = reverse('sg_examples_default')
        return self.request_path.startswith(docs_url)


class SimpleCrispyFormSGExample(BaseSGTab):
    title = gettext_noop("Simple Crispy Form")
    view = DefaultSimpleCrispyFormSectionView.urlname

    url_prefix_formats = ('/styleguide/docs/simple_crispy/',)

    @property
    @memoized
    def sidebar_items(self):
        return [
            (_("Live Example"), [
                {
                    'title': SimpleCrispyFormView.page_title,
                    'url': reverse(SimpleCrispyFormView.urlname),
                },
            ]),
            (_("Documentation"), [
                {
                    'title': FormsSimpleCrispyFormExampleView.page_title,
                    'url': reverse(FormsSimpleCrispyFormExampleView.urlname),
                },
                {
                    'title': ViewsSimpleCrispyFormExampleView.page_title,
                    'url': reverse(ViewsSimpleCrispyFormExampleView.urlname),
                },
            ]),
            (_("Style Guide"), [
                {
                    'title': _("Back to Forms"),
                    'url': '%s#molecules-forms' % reverse(MoleculesStyleGuideView.urlname),
                },
            ]),
        ]


class SGExampleTab(BaseSGTab):
    title = gettext_noop("Style Guide")
    view = 'corehq.apps.styleguide.views.docs.default'

    url_prefix_formats = ('/styleguide/bootstrap3/docs/',)

    @property
    def dropdown_items(self):
        submenu_context = [
            dropdown_dict(_("Examples"), is_header=True),
            dropdown_dict(
                _("Simple Crispy Form"),
                url=reverse(DefaultSimpleCrispyFormSectionView.urlname)
            ),
            self.divider,
            dropdown_dict(
                _("Style Guide"),
                url=reverse(MainStyleGuideView.urlname)
            ),
        ]
        return submenu_context

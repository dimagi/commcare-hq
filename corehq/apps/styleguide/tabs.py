from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop, ugettext as _
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.hqwebapp.models import UITab, format_submenu_context
from corehq.apps.styleguide.examples.simple_crispy_form.views import (
    DefaultSimpleCrispyFormSectionView,
    SimpleCrispyFormView,
)
from corehq.apps.styleguide.views import (
    MainStyleGuideView,
    FormsStyleGuideView,
)
from corehq.apps.styleguide.views.docs import (
    FormsSimpleCrispyFormExampleView,
    ViewsSimpleCrispyFormExampleView,
)


class BaseSGTab(UITab):

    @property
    def is_viewable(self):
        full_path = self._request.get_full_path()
        docs_url = reverse('sg_examples_default')
        return full_path.startswith(docs_url)


class SimpleCrispyFormSGExample(BaseSGTab):
    title = ugettext_noop("Simple Crispy Form")
    view = DefaultSimpleCrispyFormSectionView.urlname

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
                    'title': _("Back to Form Anatomy"),
                    'url': '%s#anatomy' % reverse(FormsStyleGuideView.urlname),
                },
            ]),
        ]


class SGExampleTab(BaseSGTab):
    title = ugettext_noop("Style Guide")
    view = 'corehq.apps.styleguide.views.docs.default'
    subtab_classes = (
        SimpleCrispyFormSGExample,
    )

    @property
    def dropdown_items(self):
        submenu_context = [
            format_submenu_context(_("Examples"), is_header=True),
            format_submenu_context(
                _("Simple Crispy Form"),
                url=reverse(DefaultSimpleCrispyFormSectionView.urlname)
            ),
            format_submenu_context(None, is_divider=True),
            format_submenu_context(
                _("Style Guide"),
                url=reverse(MainStyleGuideView.urlname)
            ),
        ]
        return submenu_context


from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop, ugettext as _

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.styleguide.examples.controls_demo.views import (
    DefaultControlsDemoFormsView,
    SelectControlDemoView,
)
from corehq.apps.hqwebapp.models import UITab, dropdown_dict
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
    SelectControlFormExampleView,
    SelectControlViewExampleView,
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


class ControlsDemoSGExample(BaseSGTab):
    title = ugettext_noop("Form Controls")
    view = DefaultControlsDemoFormsView.urlname

    @property
    @memoized
    def sidebar_items(self):
        return [
            (_("Live Examples"), [
                {
                    'title': SelectControlDemoView.page_title,
                    'url': reverse(SelectControlDemoView.urlname),
                },
            ]),
            (_("Documentation"), [
                {
                    'title': SelectControlFormExampleView.page_title,
                    'url': reverse(FormsSimpleCrispyFormExampleView.urlname),
                },
                {
                    'title': SelectControlViewExampleView.page_title,
                    'url': reverse(ViewsSimpleCrispyFormExampleView.urlname),
                },
            ]),
            (_("Style Guide"), [
                {
                    'title': _("Back to Form Controls"),
                    'url': '%s#form-controls' % reverse(
                        FormsStyleGuideView.urlname),
                },
            ]),
        ]


class SGExampleTab(BaseSGTab):
    title = ugettext_noop("Style Guide")
    view = 'corehq.apps.styleguide.views.docs.default'
    subtab_classes = (
        SimpleCrispyFormSGExample,
        ControlsDemoSGExample,
    )

    @property
    def dropdown_items(self):
        submenu_context = [
            dropdown_dict(_("Examples"), is_header=True),
            dropdown_dict(
                _("Simple Crispy Form"),
                url=reverse(DefaultSimpleCrispyFormSectionView.urlname)
            ),
            dropdown_dict(
                _("Form Controls"),
                url=reverse(DefaultControlsDemoFormsView.urlname)
            ),
            dropdown_dict(None, is_divider=True),
            dropdown_dict(
                _("Style Guide"),
                url=reverse(MainStyleGuideView.urlname)
            ),
        ]
        return submenu_context


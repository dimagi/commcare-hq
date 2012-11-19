from corehq.apps.reports.display import FormType
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter
# For translations
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from corehq.apps.reports.util import all_forms_in_domain
from dimagi.utils.couch.database import get_db

class FormsByApplicationFilter(BaseDrilldownOptionFilter):
    slug = "form"
    label = ugettext_noop("Filter Forms")

    @property
    def option_map(self):
        xmlns_available = all_forms_in_domain(self.domain)
        form_types = [FormType(self.domain, xmlns) for xmlns in xmlns_available]


        for xmlns in xmlns_available:
            ftype = FormType(self.domain, xmlns)
            print "App Name", ftype.app_name, ftype.app_id
            print "module", ftype.module_name, ftype.module_id
        option_map = [
            dict(
                val='app1',
                text='MCH',
                next=[
                    dict(
                        val='mod1',
                        text='Module A',
                        next=[
                            dict(
                                val='form1',
                                text='Form A'
                            )
                        ]
                    ),
                    dict(
                        val='mod2',
                        text='Module B',
                        next=[
                            dict(
                                val='form1',
                                text='Form A'
                            ),
                            dict(
                                val='form2',
                                text='Form B'
                            )
                        ]
                    )
                ]
            ),
            dict(
                val='app2',
                text='MCI',
                next=[
                    dict(
                        val='mod1',
                        text='Module Foo',
                        next=[
                            dict(
                                val='form1',
                                text='Form Bar'
                            ),
                            dict(
                                val='form2',
                                text='Form Baz'
                            )
                        ]
                    ),
                ]
            )
        ]
        return option_map

    @classmethod
    def labels(cls):
        return [
            (_('Application'), _("Select an Application") if cls.use_only_last else _("Show Forms in all Applications"), 'app_id'),
            (_('Module'), _("Select a Module") if cls.use_only_last else _("Show Forms from all Modules in selected Application"), 'module_id'),
            (_('Form'), _("Select a Form") if cls.use_only_last else _("Show all Forms in selected Module"), 'xmlns'),
        ]



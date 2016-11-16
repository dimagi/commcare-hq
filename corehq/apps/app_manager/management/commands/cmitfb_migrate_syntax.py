import logging
import re

from django.core.management.base import BaseCommand
from optparse import make_option

from corehq.toggles import all_toggles
from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.util import ParentCasePropertyBuilder, save_xform

logger = logging.getLogger('cmitfb_migrate_syntax')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = '''
        Migrate apps using vellum case management from the old
        #case/type/property syntax to the new #case/relationship/property syntax.

        Pass --save to actually save changes.
    '''

    option_list = (
        make_option('--save',
                    action='store_true',
                    dest='save',
                    help='Save changes to forms.'),
    )

    affixes = ["", "parent/", "grandparent/"]

    def _form_error(self, form, error=""):
        logger.error("{} (domain {}, app {}, form {})".format(error, form.get_app().domain,
                                                              form.get_app().id, form.unique_id))

    def _replace_in_form(self, form, relationships, case_type, affix_index):
        if not case_type:
            return
        if affix_index < len(self.affixes):
            #logger.info("Replacing #case/{}/ with #case/{}".format(case_type, self.affixes[affix_index]))
            form.source = form.source.replace("#case/{}/".format(case_type),
                                              "#case/{}".format(self.affixes[affix_index]))
            parents = relationships[case_type].get("parent", [])
            if len(parents) > 1:
                self._form_error(form, "Multiple parents: {}".format(", ".join(parents)))
            elif len(parents) == 1:
                self._replace_in_form(form, relationships, parents[0], affix_index + 1)
        else:
            self._form_error(form, "Hierarchy too deep")

    def handle(self, *args, **options):
        toggle_map = dict([(t.slug, t) for t in all_toggles()])
        domains = [row['key'] for row in Domain.get_all(include_docs=False)]
        for domain in domains:
            if toggle_map['rich_text'].enabled(domain) or toggle_map['experimental_ui'].enabled(domain):
                #logger.info('migrating domain {}'.format(domain))
                apps = get_apps_in_domain(domain, include_remote=False)
                for app in apps:
                    app_dirty = False
                    builder = ParentCasePropertyBuilder(app)
                    relationships = builder.get_parent_type_map(app.get_case_types(), allow_multiple_parents=True)
                    for module in app.modules:
                        for form in module.forms:
                            if form.doc_type == 'Form' and form.requires_case():
                                #logger.info('migrating form {}'.format(form.name.get('en', form.name)))
                                base_case_type = form.get_module().case_type
                                self._replace_in_form(form, relationships, base_case_type, 0)
                                prefixes = re.findall(r'#case/\w+/', form.source)
                                prefixes = set(prefixes)
                                for p in prefixes:
                                    if p != "#case/parent/" and p != "#case/grandparent/":
                                        self._form_error(form, "Unknown prefix remaining: {}".format(p))
                                if options['save']:
                                    try:
                                        save_xform(form.get_app(), form, form.source)
                                        app_dirty = True
                                    except:
                                        self._form_error(form, "Form xml invalid")
                    if app_dirty:
                        app.save()
        logger.info('done with cmitfb_migrate_syntax')

from collections import namedtuple

from django.core.management.base import BaseCommand

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.dbaccessors import wrap_app
from corehq.apps.app_manager.management.commands.helpers import get_all_app_ids
from corehq.util.log import with_progress_bar

QuestionInfo = namedtuple("QuestionInfo", "domain app_id module_name form_name ref")


class Command(BaseCommand):
    help = ("Pull all of the questions using a particular appearance attribute")

    def add_arguments(self, parser):
        parser.add_argument('attr')
        parser.add_argument('domains', nargs='+')
        parser.add_argument(
            '-i',
            '--include-builds',
            action='store_true',
            dest='include_builds',
            help='Include saved builds, not just current apps',
        )

    def visit(self, node, form):
        for child in node.findall('*'):
            self.visit(child, form)
            appearance = child.attrib.get('appearance')
            if appearance and self.attr in appearance:
                app = form.get_app()
                module = form.get_module()
                self.results.append(QuestionInfo(app.domain,
                                                 app.get_id,
                                                 module.default_name(),
                                                 form.default_name(),
                                                 child.attrib.get('ref')))

    def handle(self, attr, domains, **options):
        include_builds = options['include_builds']

        self.attr = attr
        self.results = []
        for domain in with_progress_bar(domains, length=len(domains)):
            app_ids = get_all_app_ids(domain, include_builds=include_builds)
            for app_id in app_ids:
                app = wrap_app(Application.get_db().get(app_id))
                for module in app.get_modules():
                    for form in module.get_forms():
                        self.visit(form.wrapped_xform().find('{h}body'), form)

        result_domains = {b.domain for b in self.results}
        result_apps = {b.app_id for b in self.results}
        print(f"Found {len(self.results)} properties in {len(result_apps)} apps in {len(result_domains)} domains")
        for result in self.results:
            print(result)

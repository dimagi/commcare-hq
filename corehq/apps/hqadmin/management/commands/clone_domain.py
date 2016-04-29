from optparse import make_option

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain, get_datasources_for_domain

types = [
    "feature_flags",
    'fixtures',
    'locations',
    'products',
    'ucr',
    'apps',
    'user_fields',
    'reminders',
    'keywords',
    'auto_case_updates',
]


class Command(BaseCommand):
    args = "<existing_domain> <new_domain>"
    help = """Clone a domain and it's data (settings, fixtures, locations, products, UCR, apps)"""

    option_list = BaseCommand.option_list + (
        make_option("-i", "--include", dest="include", action="append", choices=types),
        make_option("-e", "--exclude", dest="exclude", action="append", choices=types),
    )

    _report_map = None

    def _clone_type(self, options, type_):
        return (
                   not options['include'] or type_ in options['include']
               ) and type_ not in (options['exclude'] or [])

    def handle(self, *args, **options):
        self.existing_domain, self.new_domain = args
        self.clone_domain_and_settings()

        if self._clone_type(options, 'feature_flags'):
            self.set_flags()

        if self._clone_type(options, 'fixtures'):
            self.copy_fixtures()

        if self._clone_type(options, 'locations'):
            self.copy_locations()

        if self._clone_type(options, 'products'):
            self.copy_products()

        if self._clone_type(options, 'ucr'):
            self.copy_ucr_data()

        if self._clone_type(options, 'apps'):
            self.copy_applications()

        if self._clone_type(options, 'user_fields'):
            from corehq.apps.users.views.mobile import UserFieldsView
            self._copy_custom_data(UserFieldsView.field_type)

        if self._clone_type(options, 'reminders'):
            from corehq.apps.reminders.models import CaseReminderHandler
            self._copy_all_docs_of_type(CaseReminderHandler)

        if self._clone_type(options, 'keywords'):
            from corehq.apps.reminders.models import SurveyKeyword
            self._copy_all_docs_of_type(SurveyKeyword)

        if self._clone_type(options, 'auto_case_updates'):
            self.copy_auto_case_update_rules()

    def clone_domain_and_settings(self):
        from corehq.apps.domain.models import Domain
        new_domain_obj = Domain.get_by_name(self.new_domain)
        if new_domain_obj:
            if raw_input(
                '{} domain already exists. Do you still want to continue? [y/n]'.format(self.new_domain)
            ).lower() == 'y':
                return
            else:
                raise CommandError('abort')

        domain = Domain.get_by_name(self.existing_domain)
        domain.name = self.new_domain
        self.save_couch_copy(domain)

        from corehq.apps.commtrack.models import CommtrackConfig
        commtrack_config = CommtrackConfig.for_domain(self.existing_domain)
        self.save_couch_copy(commtrack_config, self.new_domain)

    def set_flags(self):
        from corehq.toggles import all_toggles, NAMESPACE_DOMAIN
        from corehq.feature_previews import all_previews
        from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_js_domain_cachebuster

        for toggle in all_toggles():
            if toggle.enabled(self.existing_domain):
                toggle.set(self.new_domain, True, NAMESPACE_DOMAIN)

        for preview in all_previews():
            if preview.enabled(self.existing_domain):
                preview.set(self.new_domain, True, NAMESPACE_DOMAIN)
                if preview.save_fn is not None:
                    preview.save_fn(self.new_domain, True)

        toggle_js_domain_cachebuster.clear(self.new_domain)

    def copy_fixtures(self):
        from corehq.apps.fixtures.models import FixtureDataItem
        from corehq.apps.fixtures.dbaccessors import get_fixture_data_types_in_domain

        fixture_types = get_fixture_data_types_in_domain(self.existing_domain)
        for fixture_type in fixture_types:
            old_id, new_id = self.save_couch_copy(fixture_type, self.new_domain)
            for item in FixtureDataItem.by_data_type(self.existing_domain, old_id):
                item.data_type_id = new_id
                self.save_couch_copy(item, self.new_domain)

        # TODO: FixtureOwnership - requires copying users & groups

    def copy_locations(self):
        from corehq.apps.locations.models import LocationType
        from corehq.apps.locations.models import Location
        from corehq.apps.locations.views import LocationFieldsView

        self._copy_custom_data(LocationFieldsView.field_type)

        location_types = LocationType.objects.filter(domain=self.existing_domain)
        for location_type in location_types:
            self.save_sql_copy(location_type, self.new_domain)

        def copy_location_hierarchy(location, id_map):
            new_lineage = []
            for ancestor in location.lineage:
                try:
                    new_lineage.append(id_map[ancestor])
                except KeyError:
                    self.stderr.write("Ancestor {} for location {} missing".format(location._id, ancestor))
            location.lineage = new_lineage

            old_type_name = location.location_type_name
            location._sql_location_type = LocationType.objects.get(
                domain=self.new_domain,
                name=old_type_name,
            )
            children = location.children
            old_id, new_id = self.save_couch_copy(location, self.new_domain)
            id_map[old_id] = new_id
            for child in children:
                copy_location_hierarchy(child, id_map)

        locations = Location.root_locations(self.existing_domain)
        for location in locations:
            copy_location_hierarchy(location, {})

    def copy_products(self):
        from corehq.apps.products.models import Product
        from corehq.apps.programs.models import Program
        from corehq.apps.products.views import ProductFieldsView

        self._copy_custom_data(ProductFieldsView.field_type)

        program_map = {}
        programs = Program.by_domain(self.existing_domain)
        for program in programs:
            old_id, new_id = self.save_couch_copy(program, self.new_domain)
            program_map[old_id] = new_id

        products = Product.by_domain(self.existing_domain)
        for product in products:
            if product.program_id:
                try:
                    product.program_id = program_map[product.program_id]
                except:
                    self.stderr('Missing program {} for product {}'.format(product.program_id, product._id))
            self.save_couch_copy(product, self.new_domain)

    @property
    def report_map(self):
        if not self._report_map:
            self.copy_ucr_data(self.existing_domain, self.new_domain)
        return self._report_map

    def copy_applications(self):
        from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
        from corehq.apps.app_manager.models import ReportModule
        from corehq.apps.app_manager.models import import_app
        apps = get_apps_in_domain(self.existing_domain)
        for app in apps:
            for module in app.modules:
                if isinstance(module, ReportModule):
                    for config in module.report_configs:
                        config.report_id = self.report_map[config.report_id]

            new_app = import_app(app.to_json(), self.new_domain)
            self.log_copy(app.doc_type, app._id, new_app._id)

    def copy_ucr_data(self):
        datasource_map = self.copy_ucr_datasources()
        report_map = self.copy_ucr_reports(datasource_map)
        self._report_map = report_map

    def copy_ucr_reports(self, datasource_map):
        report_map = {}
        reports = get_report_configs_for_domain(self.existing_domain)
        for report in reports:
            old_datasource_id = report.config_id
            try:
                report.config_id = datasource_map[old_datasource_id]
            except KeyError:
                pass  # datasource not found

            old_id, new_id = self.save_couch_copy(report, self.new_domain)
            report_map[old_id] = new_id
        return report_map

    def copy_ucr_datasources(self):
        datasource_map = {}
        datasources = get_datasources_for_domain(self.existing_domain)
        for datasource in datasources:
            datasource.meta.build.finished = False
            datasource.meta.build.initiated = None

            old_id, new_id = self.save_couch_copy(datasource, self.new_domain)
            datasource_map[old_id] = new_id
        return datasource_map

    def copy_auto_case_update_rules(self):
        from corehq.apps.data_interfaces.models import AutomaticUpdateRule
        update_rules = AutomaticUpdateRule.objects.filter(deleted=False, domain=self.existing_domain)
        for rule in update_rules:
            criteria = list(rule.automaticupdaterulecriteria_set.all())
            actions = rule.automaticupdateaction_set.all()

            self.save_sql_copy(rule, self.new_domain)
            for crit in criteria:
                crit.rule = rule
                self.save_sql_copy(crit, self.new_domain)

            for action in actions:
                action.rule = rule
                self.save_sql_copy(action, self.new_domain)

    def _copy_custom_data(self, type_):
        from corehq.apps.custom_data_fields.dbaccessors import get_by_domain_and_type
        doc = get_by_domain_and_type(self.existing_domain, type_)
        if doc:
            self.save_couch_copy(doc, self.new_domain)

    def _copy_all_docs_of_type(self, doc_class):
        from corehq.apps.domain.dbaccessors import get_docs_in_domain_by_class
        for doc in get_docs_in_domain_by_class(self.existing_domain, doc_class):
            self.save_couch_copy(doc, self.new_domain)

    def save_couch_copy(self, doc, new_domain=None):
        old_id = doc._id
        doc._id = doc.get_db().server.next_uuid()
        del doc['_rev']
        if new_domain:
            doc.domain = new_domain

        attachments = {}
        if "_attachments" in doc and doc['_attachments']:
            attachemnt_stubs = doc["_attachments"]
            del doc['_attachments']
            attachments = {k: doc.get_db().fetch_attachment(old_id, k) for k in attachemnt_stubs}

        doc.save()

        for k, attach in attachments.items():
            doc.put_attachment(attach, name=k, content_type=attachemnt_stubs[k]["content_type"])


        new_id = doc._id
        self.log_copy(doc.doc_type, old_id, new_id)
        return old_id, new_id

    def save_sql_copy(self, model, new_domain):
        old_id = model.id
        model.domain = new_domain
        model.id = None
        model.save()
        new_id = model.id
        self.log_copy(model.__class__.__name__, old_id, new_id)
        return old_id, new_id

    def log_copy(self, name, old_id, new_id):
        self.stdout.write("{name}(id={old_id}) -> {name}(id={new_id})".format(
            name=name, old_id=old_id, new_id=new_id
        ))

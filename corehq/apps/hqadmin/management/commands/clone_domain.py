from django.core.management.base import LabelCommand

from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain, get_datasources_for_domain


class Command(LabelCommand):
    help = """Create a new domain or update an existing domain to match the settings and data of another domain"""

    def handle(self, *args, **options):
        # feature flags
        # feature previews
        # domain settings
        # apps
        # fixtures?
        # locations?
        # products?
        # UCR's
        #
        pass


def copy_applications(old_domain, new_domain, report_map):
    from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
    from corehq.apps.app_manager.models import ReportModule
    app_map = {}
    apps = get_apps_in_domain(old_domain)
    for app in apps:
        for module in app.modules:
            if module.module_type == ReportModule.module_type:
                for config in module.report_configs:
                    config.report_id = report_map[config.report_id]

        old_id, new_id = save_copy(app, new_domain)
        app_map[old_id] = new_id
    return app_map


def copy_ucr_data(old_domain, new_domain):
    datasource_map = copy_ucr_datasources(new_domain, old_domain)
    report_map = copy_ucr_reports(datasource_map, new_domain)
    return report_map


def copy_ucr_reports(datasource_map, new_domain):
    report_map = {}
    reports = get_report_configs_for_domain('icds-sql')
    for report in reports:
        old_datasource_id = report.config_id
        try:
            report.config_id = datasource_map[old_datasource_id]
        except KeyError:
            pass  # datasource not found

        old_id, new_id = save_copy(report, new_domain)
        report_map[old_id] = new_id
    return report_map


def copy_ucr_datasources(new_domain, old_domain):
    datasource_map = {}
    datasources = get_datasources_for_domain(old_domain)
    for datasource in datasources:
        datasource.meta.build.finished = False
        datasource.meta.build.initiated = None

        old_id, new_id = save_copy(datasource, new_domain)
        datasource_map[old_id] = new_id
    return datasource_map


def save_copy(doc, new_domain):
    old_id = doc['_id']
    del doc['_id']
    del doc['_rev']
    doc.domain = new_domain
    doc.save()
    return old_id, doc['_id']

import csv
from django.core.management import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain
from corehq.apps.domain.calculations import cases, forms
from corehq.apps.domain.models import Domain
from corehq.apps.es.apps import AppES
from corehq.apps.es.cases import CaseES
from corehq.apps.es.domains import DomainES
from corehq.apps.es.forms import FormES
from corehq.apps.es.groups import GroupES
from corehq.apps.es.users import UserES
from corehq.apps.groups.dbaccessors import get_group_ids_by_domain
from corehq.apps.users.dbaccessors.all_commcare_users import get_all_user_ids_by_domain
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors


class Command(BaseCommand):
    help = "Compares the number of documents in ES to primary DB to detect inconsistency"

    def add_arguments(self, parser):
        parser.add_argument('--domain', dest='domain', default=None)
        parser.add_argument('--filename', dest='filename', default='es_reliability.csv')

    def handle(self, *args, **options):
        with open(options['filename'], 'w') as csvfile:
            writer = csv.writer(csvfile)

            if options['domain']:
                self.deep_dive_domain(options['domain'], writer)
            else:
                self.check_domains(writer)

    def deep_dive_domain(self, domain, csvfile):
        csvfile.writerow(['domain', 'doctype', 'docs_in_es_not_primary', 'docs_in_primary_db_not_es'])
        num_cases_es = cases(domain)
        num_forms_es = forms(domain)
        num_apps_es = AppES().domain(domain).is_build(False).count()
        num_users_es = UserES().domain(domain).count()
        num_groups_es = GroupES().domain(domain).count()
        num_cases_primary = cases(domain, primary_db=True)
        num_forms_primary = forms(domain, primary_db=True)
        app_ids_primary = set(get_app_ids_in_domain(domain))
        num_apps_primary = len(app_ids_primary)
        user_ids_primary = set(get_all_user_ids_by_domain(domain))
        num_users_primary = len(user_ids_primary)
        group_ids_primary = set(get_group_ids_by_domain(domain))
        num_groups_primary = len(group_ids_primary)

        if num_cases_es != num_cases_primary:
            case_ids_es = set(CaseES().domain(domain).get_ids())
            case_ids_primary = set(CaseAccessors(domain).get_case_ids_in_domain())
            csvfile.writerow([domain, 'cases', case_ids_es - case_ids_primary, case_ids_primary - case_ids_es])
        if num_forms_es != num_forms_primary:
            form_ids_es = set(FormES().domain(domain).get_ids())
            form_ids_primary = set(FormAccessors(domain).get_all_form_ids_in_domain(domain))
            csvfile.writerow([domain, 'forms', form_ids_es - form_ids_primary, form_ids_primary - form_ids_es])
        if num_apps_es != num_apps_primary:
            app_ids_es = set(AppES().domain(domain).is_build(False).get_ids())
            csvfile.writerow([domain, 'apps', app_ids_es - app_ids_primary, app_ids_primary - app_ids_es])
        if num_users_es != num_users_primary:
            user_ids_es = set(UserES().domain(domain).get_ids())
            csvfile.writerow([domain, 'users', user_ids_es - user_ids_primary, user_ids_primary - user_ids_es])
        if num_groups_es != num_groups_primary:
            group_ids_es = set(GroupES().domain(domain).get_ids())
            csvfile.writerow([domain, 'groups', group_ids_es - group_ids_primary, group_ids_primary - group_ids_es])

    def check_domains(self, csvfile):
        csvfile.writerow(['domain', 'doctype', 'docs_in_es', 'docs_in_primary_db'])
        num_domains_es = DomainES().count()
        num_domains_couch = Domain.get_db().view("domain/domains").all()[0]['value']

        if num_domains_es != num_domains_couch:
            # not a great start here
            csvfile.writerow(["HQ", 'domains', num_domains_es, num_domains_couch])

        domains = DomainES().fields(["name"]).scroll()
        for domain in domains:
            self.check_domain(domain['name'], csvfile)

    def check_domain(self, domain, csvfile):
        num_cases_es = cases(domain)
        num_forms_es = forms(domain)
        num_apps_es = AppES().domain(domain).is_build(False).count()
        num_users_es = UserES().domain(domain).count()
        num_groups_es = GroupES().domain(domain).count()
        num_cases_primary = cases(domain, primary_db=True)
        num_forms_primary = forms(domain, primary_db=True)
        num_apps_primary = len(get_app_ids_in_domain(domain))
        num_users_primary = len(list(get_all_user_ids_by_domain(domain)))
        num_groups_primary = len(list(get_group_ids_by_domain(domain)))

        if num_cases_es != num_cases_primary:
            csvfile.writerow([domain, 'cases', num_cases_es, num_cases_primary])
        if num_forms_es != num_forms_primary:
            csvfile.writerow([domain, 'forms', num_forms_es, num_forms_primary])
        if num_apps_es != num_apps_primary:
            csvfile.writerow([domain, 'apps', num_apps_es, num_apps_primary])
        if num_users_es != num_users_primary:
            csvfile.writerow([domain, 'users', num_users_es, num_users_primary])
        if num_groups_es != num_groups_primary:
            csvfile.writerow([domain, 'groups', num_groups_es, num_groups_primary])

from collections import namedtuple
import csv
import json
import logging
from django.core.management import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain
from corehq.apps.domain.calculations import cases
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


logger = logging.getLogger('es_reliability')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = "Compares the number of documents in ES to primary DB to detect inconsistency"

    def add_arguments(self, parser):
        parser.add_argument('--all-domains', dest='all_domains', default=False, action="store_true")
        parser.add_argument('--domain', dest='domain', default=None)
        parser.add_argument('--filename', dest='filename', default='es_reliability.csv')

    def handle(self, *args, **options):
        with open(options['filename'], 'w') as csvfile:
            writer = csv.writer(csvfile)

            if options['domain']:
                self.deep_dive_domain(options['domain'], writer)
            else:
                self.check_domains(options['all_domains'], writer)

    def deep_dive_domain(self, domain, csvfile):
        def _write_row(doc_type, extra_in_es, extra_in_primary):
            csvfile.writerow([domain, doc_type, json.dumps(list(extra_in_es)), json.dumps(list(extra_in_primary))])

        csvfile.writerow(['domain', 'doctype', 'docs_in_es_not_primary', 'docs_in_primary_db_not_es'])
        stats = self.domain_info(domain)

        if stats.num_cases_es != stats.num_cases_primary:
            case_ids_es = set(CaseES().domain(domain).get_ids())
            case_ids_primary = set(CaseAccessors(domain).get_case_ids_in_domain())
            extra_in_es = case_ids_es - case_ids_primary
            extra_in_primary = case_ids_primary - case_ids_es
            _write_row('cases', extra_in_es, extra_in_primary)
            csvfile.writerow([domain, 'cases', extra_in_es, extra_in_primary])

        if stats.num_forms_es != stats.num_forms_primary:
            form_ids_es = set(form_query(domain).get_ids())
            form_ids_primary = set(FormAccessors(domain).get_all_form_ids_in_domain())
            extra_in_es = form_ids_es - form_ids_primary
            extra_in_primary = form_ids_primary - form_ids_es
            _write_row('forms', extra_in_es, extra_in_primary)

        if stats.num_apps_es != stats.num_apps_primary:
            app_ids_es = set(app_query(domain).get_ids())
            extra_in_es = app_ids_es - stats.app_ids_primary
            extra_in_primary = stats.app_ids_primary - app_ids_es
            _write_row('apps', extra_in_es, extra_in_primary)

        if stats.num_users_es != stats.num_users_primary:
            user_ids_es = set(user_query(domain).get_ids())
            extra_in_es = user_ids_es - stats.user_ids_primary
            extra_in_primary = stats.user_ids_primary - user_ids_es
            _write_row('users', extra_in_es, extra_in_primary)

        if stats.num_groups_es != stats.num_groups_primary:
            group_ids_es = set(GroupES().domain(domain).get_ids())
            extra_in_es = group_ids_es - stats.group_ids_primary
            extra_in_primary = stats.group_ids_primary - group_ids_es
            _write_row('groups', extra_in_es, extra_in_primary)

    def check_domains(self, all_domains, csvfile):
        csvfile.writerow(['domain', 'doctype', 'docs_in_es', 'docs_in_primary_db'])
        num_domains_es = DomainES().count()
        num_domains_couch = Domain.get_db().view("domain/domains").all()[0]['value']

        if num_domains_es != num_domains_couch:
            # not a great start here
            csvfile.writerow(["HQ", 'domains', num_domains_es, num_domains_couch])

        domain_query = DomainES().fields(['name'])
        if not all_domains:
            domain_query = domain_query.is_active_project()
        domains = domain_query.scroll()
        for domain in domains:
            try:
                self.check_domain(domain['name'], csvfile)
            except:
                logger.error('error occurred when checking domain {}'.format(domain['name']))

    def check_domain(self, domain, csvfile):
        stats = self.domain_info(domain)

        if stats.num_cases_es != stats.num_cases_primary:
            csvfile.writerow([domain, 'cases', stats.num_cases_es, stats.num_cases_primary])
        if stats.num_forms_es != stats.num_forms_primary:
            csvfile.writerow([domain, 'forms', stats.num_forms_es, stats.num_forms_primary])
        if stats.num_apps_es != stats.num_apps_primary:
            csvfile.writerow([domain, 'apps', stats.num_apps_es, stats.num_apps_primary])
        if stats.num_users_es != stats.num_users_primary:
            csvfile.writerow([domain, 'users', stats.num_users_es, stats.num_users_primary])
        if stats.num_groups_es != stats.num_groups_primary:
            csvfile.writerow([domain, 'groups', stats.num_groups_es, stats.num_groups_primary])

    def domain_info(self, domain):
        DomainStats = namedtuple('DomainStats', [
            'num_cases_es', 'num_forms_es', 'num_apps_es', 'num_users_es', 'num_groups_es',
            'num_cases_primary', 'num_forms_primary', 'num_apps_primary', 'num_users_primary', 'num_groups_primary',
            'app_ids_primary', 'user_ids_primary', 'group_ids_primary'
        ])

        num_cases_primary = CaseAccessors(domain).get_number_of_cases_in_domain()
        num_forms_primary = FormAccessors(domain).get_number_of_forms_in_domain()
        app_ids_primary = set(get_app_ids_in_domain(domain))
        user_ids_primary = set(get_all_user_ids_by_domain(domain))
        group_ids_primary = set(get_group_ids_by_domain(domain))

        stats = DomainStats(
            num_cases_es=cases(domain),
            num_forms_es=form_query(domain).count(),
            num_apps_es=app_query(domain).count(),
            num_users_es=user_query(domain).count(),
            num_groups_es=GroupES().domain(domain).count(),
            num_cases_primary=num_cases_primary,
            num_forms_primary=num_forms_primary,
            app_ids_primary=app_ids_primary,
            num_apps_primary=len(app_ids_primary),
            user_ids_primary=user_ids_primary,
            num_users_primary=len(user_ids_primary),
            group_ids_primary=group_ids_primary,
            num_groups_primary=len(group_ids_primary),
        )

        return stats


def user_query(domain):
    return UserES().domain(domain).show_inactive()


def app_query(domain):
    return AppES().domain(domain).is_build(False)


def form_query(domain):
    return FormES().domain(domain).remove_default_filter('has_user')

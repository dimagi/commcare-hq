from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import csv
from collections import defaultdict

from django.apps import apps
from django.core.management import BaseCommand
from django.conf import settings
from importlib import import_module

from corehq.apps.accounting.models import Subscription, SoftwarePlanEdition
from corehq.apps.domain.models import Domain
import six
from six.moves import map
from io import open


class Command(BaseCommand):

    def handle(self, **kwargs):
        domains_by_module = defaultdict(list)
        for domain, module in settings.DOMAIN_MODULE_MAP.items():
            domains_by_module[module].append(domain)

        with open("custom-modules.csv", "w") as f:
            writer = csv.writer(f)
            writer.writerow([
                'module',
                'path',
                'domains',
                'domains exist',
                'plans',
                'in DOMAIN_MODULE_MAP',
                'likely removable',
            ])
            visited_paths = set()
            for module, domains in domains_by_module.items():

                try:
                    path = import_module(module).__path__[0]
                except ImportError:
                    path = "PATH NOT FOUND"
                visited_paths.add(path)

                writer.writerow(self.log_module_info(module, path, domains, in_module_map=True))

            for app_config in apps.get_app_configs():
                if (app_config.path.startswith(settings.FILEPATH + "/custom")
                        and app_config.path not in visited_paths):
                    # Just check and see if the label corresponds to a domain
                    writer.writerow(
                        self.log_module_info(
                            app_config.label,
                            app_config.path,
                            [app_config.label],
                            in_module_map=False
                        )
                    )

    def log_module_info(self, module, path, domains, in_module_map):
        domains_exist = []
        plans = []
        all_community = True
        for domain in domains:
            domain_obj = Domain.get_by_name(domain)
            plan = "Not Found"
            domains_exist.append(domain_obj is not None)
            if domain_obj:
                subscription = Subscription.get_active_subscription_by_domain(domain)
                if subscription:
                    plan = subscription.plan_version.plan.name
                    if subscription.plan_version.plan.edition != SoftwarePlanEdition.COMMUNITY:
                        all_community = False
            plans.append(plan)

        return [
            module,
            path[len(settings.FILEPATH) + 1:],
            " | ".join(domains),
            " | ".join(map(six.text_type, domains_exist)),
            " | ".join(plans),
            in_module_map,
            all(domains_exist) and all_community,
        ]

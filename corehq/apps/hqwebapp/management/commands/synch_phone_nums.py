from __future__ import absolute_import
from __future__ import unicode_literals
import os
import json

from django.core.management.base import BaseCommand

from corehq.apps.users.models import CommCareUser
from corehq.apps.sms.tasks import sync_user_phone_numbers as sms_sync_user_phone_numbers
from corehq.form_processor.models import CommCareCaseSQL
from corehq.messaging.tasks import sync_case_for_messaging
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


class Command(BaseCommand):
    help = "Resync all contacts' phone numbers for given projects"

    def add_arguments(self, parser):
        parser.add_argument('-p', '--projects', type=str, help='Comma separated project list')

    def handle(self,  **kwargs):
        projects = kwargs['projects'].split(',')
        db_aliases = get_db_aliases_for_partitioned_query()
        db_aliases.sort()

        for domain in projects:
            print("Resync all contacts' phone numbers for project %s  " % domain)
            print("Synching for phone numbers")
            commcare_user_ids = (
                    CommCareUser.ids_by_domain(domain, is_active=True) +
                    CommCareUser.ids_by_domain(domain, is_active=False)
            )
            for user_id in commcare_user_ids:
                sms_sync_user_phone_numbers.delay(user_id)

            print("Iterating over databases: %s" % db_aliases)
            for db_alias in db_aliases:
                print("")
                print("Synching for cases in %s ..." % db_alias)
                case_ids = list(
                    CommCareCaseSQL
                    .objects
                    .using(db_alias)
                    .filter(domain=domain, deleted=False)
                    .values_list('case_id', flat=True)
                )
                for case_id in case_ids:
                    sync_case_for_messaging.delay(domain, case_id)

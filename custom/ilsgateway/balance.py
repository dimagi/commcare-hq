from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.mixin import apply_leniency, VerifiedNumber
from corehq.apps.users.models import WebUser, CommCareUser, UserRole
from custom.ilsgateway.models import ILSMigrationStats, ILSMigrationProblem
from custom.logistics.mixin import UserMigrationMixin
from custom.logistics.utils import iterate_over_api_objects


class BalanceMigration(UserMigrationMixin):

    def __init__(self, domain, endpoint):
        self.domain = domain
        self.endpoint = endpoint

    def _get_total_counts(self, func, limit=1, **kwargs):
        meta, _ = func(limit=limit, **kwargs)
        return meta['total_count'] if meta else 0

    @transaction.atomic
    def validate_sms_users(self):
        for sms_user in iterate_over_api_objects(self.endpoint.get_smsusers):
            description = ""
            user = CommCareUser.get_by_username(self.get_username(sms_user)[0])
            if not user:
                description = "Not exists"
                ILSMigrationProblem.objects.create(
                    domain=self.domain,
                    external_id=sms_user.id,
                    object_type='smsuser',
                    description=description
                )
                continue

            if user.domain != self.domain:
                description += "domain isn't correct"

            phone_numbers = {
                apply_leniency(connection.phone_number) for connection in sms_user.phone_numbers
            }

            if phone_numbers - set(user.phone_numbers):
                description += "Invalid phone numbers, "

            phone_to_backend = {
                apply_leniency(connection.phone_number): connection.backend
                for connection in sms_user.phone_numbers
            }

            default_phone_number = [
                connection.phone_number for connection in sms_user.phone_numbers if connection.default
            ]

            default_phone_number = default_phone_number[0] if default_phone_number else None

            if default_phone_number and (apply_leniency(default_phone_number) != user.default_phone_number):
                description += "Invalid default phone number, "

            for phone_number in user.phone_numbers:
                vn = VerifiedNumber.by_phone(phone_number)
                if not vn or vn.owner_id != user.get_id or vn.domain != self.domain or not vn.verified:
                    description += "Phone number not verified, "
                else:
                    backend = phone_to_backend.get(phone_number)
                    if backend != 'push_backend' and vn.backend_id != 'MOBILE_BACKEND_TEST' \
                            or (backend == 'push_backend' and vn.backend_id):
                        description += "Invalid backend, "

            if description:
                migration_problem, _ = ILSMigrationProblem.objects.get_or_create(
                    domain=self.domain,
                    object_id=user.get_id,
                    object_type='smsuser'
                )
                migration_problem.external_id = sms_user.id
                migration_problem.description = description.rstrip(' ,')
                migration_problem.save()
            else:
                ILSMigrationProblem.objects.filter(
                    domain=self.domain,
                    external_id=sms_user.id,
                    object_type='smsuser'
                ).delete()

    @transaction.atomic
    def validate_web_users(self):
        unique_usernames = set()
        read_only_role_id = UserRole.get_read_only_role_by_domain(self.domain).get_id
        for web_user in iterate_over_api_objects(self.endpoint.get_webusers):
            description = ''
            if web_user.email:
                username = web_user.email.lower()
            else:
                username = web_user.username.lower()
                try:
                    validate_email(username)
                except ValidationError:
                    # We are not migrating users without valid email in v1
                    continue

            unique_usernames.add(username)
            couch_web_user = WebUser.get_by_username(username)
            if not couch_web_user or self.domain not in couch_web_user.get_domains():
                description = "Not exists"
                ILSMigrationProblem.objects.get_or_create(
                    domain=self.domain,
                    object_type='webuser',
                    description=description,
                    external_id=web_user.email or web_user.username
                )
                continue

            if not web_user.location:
                continue

            dm = couch_web_user.get_domain_membership(self.domain)
            try:
                sql_location = SQLLocation.objects.get(external_id=web_user.location, domain=self.domain)

                if dm.location_id != sql_location.location_id:
                    description += 'Location not assigned'
            except SQLLocation.DoesNotExist:
                # Location is inactive in v1 or it's an error in location migration
                pass

            if dm.role_id != read_only_role_id:
                description += 'Invalid role'

            if not description:
                ILSMigrationProblem.objects.filter(
                    domain=self.domain,
                    external_id=web_user.email or web_user.username
                ).delete()
            else:
                ils_migration_problem = ILSMigrationProblem.objects.get_or_create(
                    domain=self.domain,
                    object_type='webuser',
                    external_id=web_user.email or web_user.username
                )[0]
                ils_migration_problem.description = description
                ils_migration_problem.object_id = couch_web_user.get_id

        migration_stats = ILSMigrationStats.objects.get(domain=self.domain)
        migration_stats.web_users_count = len(unique_usernames)
        migration_stats.save()

    def balance_migration(self, date=None):
        products_count = self._get_total_counts(self.endpoint.get_products)
        locations_count = self._get_total_counts(
            self.endpoint.get_locations,
            filters=dict(is_active=True)
        )
        sms_users_count = self._get_total_counts(self.endpoint.get_smsusers)

        stats, _ = ILSMigrationStats.objects.get_or_create(domain=self.domain)
        stats.products_count = products_count
        stats.locations_count = locations_count
        stats.sms_users_count = sms_users_count
        stats.save()

        self.validate_web_users()
        self.validate_sms_users()

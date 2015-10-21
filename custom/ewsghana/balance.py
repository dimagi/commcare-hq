from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.mixin import apply_leniency, VerifiedNumber
from corehq.apps.users.models import CommCareUser, WebUser
from custom.ewsghana.models import EWSMigrationStats, EWSMigrationProblem, EWSExtension
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
    def validate_web_users(self, date):
        for web_user in iterate_over_api_objects(
            self.endpoint.get_webusers, filters=dict(date_joined__gte=date)
        ):
            description = ""

            if web_user.email:
                username = web_user.email.lower()
            else:
                username = web_user.username.lower()
                try:
                    validate_email(username)
                except ValidationError:
                    # We are not migrating users without valid email in v1
                    continue

            couch_web_user = WebUser.get_by_username(username)
            if not couch_web_user:
                description = "Not exists"
                EWSMigrationProblem.objects.create(
                    domain=self.domain,
                    object_type='webuser',
                    description=description,
                    external_id=web_user.email or web_user.username
                )
                continue

            user_contact = web_user.contact
            if not user_contact:
                continue

            phone_numbers = {
                apply_leniency(connection.phone_number)
                for connection in user_contact.phone_numbers
            }

            if set(phone_numbers) - set(couch_web_user.phone_numbers):
                description = "Invalid phone numbers, "

            try:
                extension = EWSExtension.objects.get(user_id=couch_web_user.get_id, domain=self.domain)
                supply_point = extension.supply_point.external_id if extension.supply_point else None
                sms_notifications = extension.sms_notifications
            except EWSExtension.DoesNotExist:
                supply_point = None
                sms_notifications = False

            if str(supply_point) != str(web_user.supply_point):
                active = True
                if not supply_point and web_user.supply_point:
                    active = self.endpoint.get_supply_point(web_user.supply_point).active

                if active:
                    print supply_point, web_user.supply_point
                    description += 'Invalid supply point, '

            if sms_notifications != web_user.sms_notifications:
                print sms_notifications, web_user.sms_notifications
                description += 'Invalid value of sms_notifications field'

            if description:
                migration_problem, _ = EWSMigrationProblem.objects.get_or_create(
                    domain=self.domain,
                    object_id=couch_web_user.get_id,
                )
                migration_problem.object_type = 'webuser'
                migration_problem.external_id = web_user.email or web_user.username
                migration_problem.description = description.rstrip(' ,')
                migration_problem.save()
            else:
                EWSMigrationProblem.objects.filter(
                    domain=self.domain,
                    external_id=web_user.email or web_user.username
                ).delete()

    @transaction.atomic
    def validate_sms_users(self, date):
        for sms_user in iterate_over_api_objects(
                self.endpoint.get_smsusers, filters=dict(date_updated__gte=date)
        ):
            description = ""
            user = CommCareUser.get_by_username(self.get_username(sms_user)[0])
            if not user:
                description = "Not exists"
                EWSMigrationProblem.objects.create(
                    domain=self.domain,
                    external_id=sms_user.id,
                    object_type='smsuser',
                    description=description
                )
                continue

            phone_numbers = {
                apply_leniency(connection.phone_number) for connection in sms_user.phone_numbers
            }

            if phone_numbers - set(user.phone_numbers):
                description += "Invalid phone numbers, "

            phone_to_backend = {
                connection.phone_number: connection.backend
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
                if not vn:
                    description += "Phone number not verified, "
                    continue
                backend = phone_to_backend.get(phone_number)
                if backend == 'message_tester' and vn.backend_id != 'MOBILE_BACKEND_TEST' \
                        or (not backend and vn.backend_id):
                    description += "Invalid backend, "

            if description:
                migration_problem, _ = EWSMigrationProblem.objects.get_or_create(
                    domain=self.domain,
                    object_id=user.get_id,
                )
                migration_problem.object_type = 'smsuser'
                migration_problem.external_id = sms_user.id
                migration_problem.description = description.rstrip(' ,')
                migration_problem.save()
            else:
                EWSMigrationProblem.objects.filter(
                    domain=self.domain,
                    external_id=sms_user.id
                ).delete()

    def balance_migration(self, date=None):
        products_count = self._get_total_counts(self.endpoint.get_products)
        district_count = self._get_total_counts(
            self.endpoint.get_locations,
            filters=dict(type='district', is_active=True)
        )
        region_count = self._get_total_counts(
            self.endpoint.get_locations,
            filters=dict(type='region', is_active=True)
        )
        country_count = self._get_total_counts(
            self.endpoint.get_locations, filters=dict(type='country', is_active=True)
        )
        supply_points_count = self._get_total_counts(self.endpoint.get_supply_points, filters=dict(active=True))
        web_users_count = self._get_total_counts(self.endpoint.get_webusers)
        sms_users_count = self._get_total_counts(self.endpoint.get_smsusers)

        stats, _ = EWSMigrationStats.objects.get_or_create(domain=self.domain)
        stats.products_count = products_count
        stats.locations_count = district_count + region_count + country_count
        stats.supply_points_count = supply_points_count
        stats.web_users_count = web_users_count
        stats.sms_users_count = sms_users_count
        stats.save()

        self.validate_web_users(date)
        self.validate_sms_users(date)

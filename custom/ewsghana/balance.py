from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from corehq.apps.commtrack.dbaccessors.supply_point_case_by_domain_external_id import \
    get_supply_point_case_by_domain_external_id
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.models import ReportNotification, ReportConfig
from corehq.apps.sms.mixin import apply_leniency, VerifiedNumber
from corehq.apps.users.models import CommCareUser, WebUser, CouchUser
from custom.ewsghana.api import EmailSettingsSync
from custom.ewsghana.models import EWSMigrationStats, EWSMigrationProblem, EWSExtension
from custom.logistics.mixin import UserMigrationMixin
from custom.logistics.utils import iterate_over_api_objects
from dimagi.utils.couch.database import iter_docs


class BalanceMigration(UserMigrationMixin):

    def __init__(self, domain, endpoint):
        self.domain = domain
        self.endpoint = endpoint

    def _get_total_counts(self, func, limit=1, **kwargs):
        meta, _ = func(limit=limit, **kwargs)
        return meta['total_count'] if meta else 0

    @transaction.atomic
    def validate_web_users(self, date=None):
        unique_usernames = set()
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

            unique_usernames.add(username)
            couch_web_user = WebUser.get_by_username(username)
            if not couch_web_user or self.domain not in couch_web_user.get_domains():
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

            default_phone_number = [
                connection.phone_number for connection in user_contact.phone_numbers if connection.default
            ]

            default_phone_number = default_phone_number[0] if default_phone_number else None

            if default_phone_number and \
                    (apply_leniency(default_phone_number) != couch_web_user.default_phone_number):
                description += "Invalid default phone number, "

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
                    description += 'Invalid supply point, '

            if sms_notifications != web_user.sms_notifications:
                description += 'Invalid value of sms_notifications field'

            if description:
                migration_problem, _ = EWSMigrationProblem.objects.get_or_create(
                    domain=self.domain,
                    object_id=couch_web_user.get_id,
                    object_type='webuser'
                )
                migration_problem.external_id = web_user.email or web_user.username
                migration_problem.description = description.rstrip(' ,')
                migration_problem.save()
            else:
                EWSMigrationProblem.objects.filter(
                    domain=self.domain,
                    external_id=web_user.email or web_user.username,
                    object_type='webuser'
                ).delete()

        migration_stats = EWSMigrationStats.objects.get(domain=self.domain)
        migration_stats.web_users_count = len(unique_usernames)
        migration_stats.save()

    @transaction.atomic
    def validate_sms_users(self):
        for sms_user in iterate_over_api_objects(self.endpoint.get_smsusers):
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
                if not vn or vn.owner_id != user.get_id:
                    description += "Phone number not verified, "
                else:
                    backend = phone_to_backend.get(phone_number)
                    if backend == 'message_tester' and vn.backend_id != 'MOBILE_BACKEND_TEST' \
                            or (backend != 'message_tester' and vn.backend_id):
                        description += "Invalid backend, "

            if description:
                migration_problem, _ = EWSMigrationProblem.objects.get_or_create(
                    domain=self.domain,
                    object_id=user.get_id,
                    object_type='smsuser'
                )
                migration_problem.external_id = sms_user.id
                migration_problem.description = description.rstrip(' ,')
                migration_problem.save()
            else:
                EWSMigrationProblem.objects.filter(
                    domain=self.domain,
                    external_id=sms_user.id,
                    object_type='smsuser'
                ).delete()

    def _check_username(self, usernames, ews_user_id):
        return any([username.endswith(str(ews_user_id)) for username in usernames])

    @transaction.atomic
    def validate_supply_points(self, date):
        for location in iterate_over_api_objects(
                self.endpoint.get_locations, filters={'is_active': True, 'date_updated__gte': date}
        ):
            for supply_point in location.supply_points:
                sp = get_supply_point_case_by_domain_external_id(self.domain, supply_point.id)
                if sp:
                    EWSMigrationProblem.objects.filter(
                        domain=self.domain, external_id=supply_point.id, object_type='supply_point'
                    ).delete()
                    sql_location = sp.sql_location
                    ids = sql_location.facilityincharge_set.all().values_list('user_id', flat=True)
                    usernames = [user['username'].split('@')[0] for user in iter_docs(CouchUser.get_db(), ids)]
                    if not all([self._check_username(usernames, incharge) for incharge in supply_point.incharges]):
                        migration_problem, _ = EWSMigrationProblem.objects.get_or_create(
                            domain=self.domain,
                            object_id=sql_location.location_id,
                            object_type='location'
                        )
                        migration_problem.object_type = 'location'
                        migration_problem.external_id = sql_location.external_id
                        migration_problem.description = 'Invalid in charges'
                        migration_problem.save()
                    else:
                        EWSMigrationProblem.objects.filter(
                            domain=self.domain,
                            external_id=sql_location.external_id,
                            object_type='location'
                        ).delete()
                elif supply_point.active and supply_point.last_reported:
                    migration_problem, _ = EWSMigrationProblem.objects.get_or_create(
                        domain=self.domain,
                        external_id=supply_point.id,
                    )
                    migration_problem.object_type = 'supply_point'
                    migration_problem.external_id = supply_point.id
                    migration_problem.description = 'Not exists'
                    migration_problem.save()

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
        sms_users_count = self._get_total_counts(self.endpoint.get_smsusers)

        stats, _ = EWSMigrationStats.objects.get_or_create(domain=self.domain)
        stats.products_count = products_count
        stats.locations_count = district_count + region_count + country_count
        stats.supply_points_count = supply_points_count
        stats.sms_users_count = sms_users_count
        stats.save()

        self.validate_supply_points(date)
        self.validate_web_users(date)
        self.validate_sms_users()

    def _check_report(self, report, reports, day, interval):
        if report.report not in EmailSettingsSync.REPORT_MAP or not report.users:
            return False
        username = report.users[0].lower()
        location_code = report.view_args.split()[1][1:-2]
        desc = "Report not migrated; "
        report_tuple = (username, day, report.hours, location_code,
                        EmailSettingsSync.REPORT_MAP[report.report], interval)
        external_id = '{}-{}-{}-{}-{}-{}'.format(*report_tuple)
        if report_tuple not in reports:
            web_user = WebUser.get_by_username(username)
            if not web_user or self.domain not in web_user.domains:
                desc += 'User {} is not active; '.format(username)
            try:
                sql_location = SQLLocation.objects.get(domain=self.domain, site_code=location_code)
                if sql_location.is_archived:
                    desc += 'Location {} is not active; '.format(location_code)
            except SQLLocation.DoesNotExist:
                desc += 'Location {} does not exist; '.format(location_code)

            migration_problem, _ = EWSMigrationProblem.objects.get_or_create(
                domain=self.domain,
                object_id=username,
                object_type='email_report',
                external_id=external_id
            )
            migration_problem.description = desc
            migration_problem.save()
        return True

    def balance_email_reports(self):
        EWSMigrationProblem.objects.filter(domain=self.domain).delete()
        reports = set()
        reports_count = 0
        for web_user in WebUser.by_domain(self.domain):
            notifications = ReportNotification.by_domain_and_owner(self.domain, web_user.get_id)
            for notification in notifications:
                config_id = notification.config_ids[0] if notification.config_ids else None

                if not config_id:
                    continue

                config = ReportConfig.get(config_id)
                location_id = config.filters.get('location_id')
                if not location_id:
                    # report is not migrated from ews
                    continue
                reports_count += 1
                report_slug = config.report_slug
                code = SQLLocation.objects.get(location_id=location_id).site_code
                report_tuple = (
                    web_user.username, notification.day, notification.hour,
                    code, report_slug, notification.interval
                )
                external_id = '{}-{}-{}-{}-{}-{}'.format(*report_tuple)
                if not notification.send_to_owner and not notification.recipient_emails:
                    migration_problem, _ = EWSMigrationProblem.objects.get_or_create(
                        domain=self.domain,
                        object_id=web_user.username,
                        object_type='email_report_send_to_owner',
                        external_id=external_id
                    )
                    migration_problem.description = 'send_to_owner not set to true'
                    migration_problem.save()

                reports.add(report_tuple)

        total_count = 0

        for report in self.endpoint.get_daily_reports(limit=1000)[1]:
            if self._check_report(report, reports, 1, 'daily'):
                total_count += 1

        for report in self.endpoint.get_weekly_reports(limit=1000)[1]:
            if self._check_report(report, reports, report.day_of_week, 'weekly'):
                total_count += 1

        for report in self.endpoint.get_monthly_reports(limit=1000)[1]:
            if self._check_report(report, reports, report.day_of_month, 'monthly'):
                total_count += 1

        if total_count != reports_count:
            migration_problem, _ = EWSMigrationProblem.objects.get_or_create(
                domain=self.domain,
                object_id=None,
                object_type='email_report',
                external_id='email-report-count'
            )
            migration_problem.description = '{} / {}'.format(reports_count, total_count)
            migration_problem.save()

from io import BytesIO
from openpyxl import Workbook
from collections import defaultdict

from dateutil.relativedelta import relativedelta
from datetime import datetime, date
from django.core.management import BaseCommand
from django.db.models import Count
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.es.domains import DomainES
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import Domain
from django.core.mail import EmailMessage
from django.conf import settings
from corehq.apps.es.users import UserES


class Command(BaseCommand):
    help = """
    Generate a worker activity report for the given months.
    """

    def add_arguments(self, parser):
        parser.add_argument('--months', default=1, type=int, help="Last X months to evaluate")
        parser.add_argument('--limit', default=10, type=int, help="Grab the top X domains by user count")
        parser.add_argument('--recipient_email', type=str, help="Email address to send the report to")

    def handle(self, *args, **options):
        months = options.get('months', 1)
        limit = options.get('limit', 10)
        recipient_email = options.get('recipient_email')

        assert months > 0, "Months must be greater than 0"
        assert months <= 12, "Months must be less than or equal to 12"
        assert limit > 0, "Limit must be greater than 0"

        if not recipient_email:
            print("Email recipient email must be provided")
            return

        months_activity = collect_worker_activity_data(months, limit)
        months_activity = augment_activity_results(months_activity)

        csv_workbook = generate_csv_report(months_activity)
        send_email_report(csv_workbook, recipient_email)


def collect_worker_activity_data(months, limit):
    """Collects user activity data across domains for ConnectID rollout planning."""
    print("Collecting worker activity data...")

    domain_names = DomainES().real_domains().values_list('name', flat=True)

    months_activity = {}
    for month in range(1, months + 1):
        print("Collecting data for month:", month)
        months_activity[f"{month}_months"] = list(get_activity_for_timeframe(month, domain_names, limit))

    return months_activity


def get_activity_for_timeframe(months, domain_names, limit):
    """Get user activity data for specific timeframe."""
    now = datetime.utcnow()
    start_date = date(now.year, now.month, now.day) - relativedelta(months=months)

    users_months_activity = (
        MALTRow.objects
        .filter(
            month__gte=start_date,
            num_of_forms__gte=1,
            domain_name__in=domain_names,
            user_type="CommCareUser",
        )
        .values("domain_name", "app_id", "user_id")
    )

    qualified_users = (
        users_months_activity
        .annotate(month_count=Count("month", distinct=True))
        .filter(month_count=months)
    )

    # Count distinct users per domain/app pair
    user_rows = list(qualified_users)
    user_map = defaultdict(set)

    for row in user_rows:
        key = (row["domain_name"], row["app_id"])
        user_map[key].add(row["user_id"])

    user_count_per_domain_app = sorted(
        [
            {"domain_name": k[0], "app_id": k[1], "user_count": len(v)}
            for k, v in user_map.items()
        ],
        key=lambda x: -x["user_count"]
    )
    return user_count_per_domain_app[:limit]


def augment_activity_results(months_activity):
    """Augment the activity data with total users per app on a domain."""
    print("Augmenting activity results...")

    domain_users_count = {}

    for _, activity_list in months_activity.items():
        for activity in activity_list:
            domain_name = activity.get('domain_name')
            app_id = activity.get('app_id')

            app_name, app_lang, domain_countries = get_app_deployment_info(domain_name, app_id)
            activity['app_name'] = app_name
            activity['default_language'] = app_lang
            activity['deployment_countries'] = domain_countries

            if domain_name not in domain_users_count:
                total_users = domain_users_count[domain_name] = (
                    UserES().domain(domain_name).mobile_users().run().total
                )
            else:
                total_users = domain_users_count[domain_name]
            activity['total_mobile_workers'] = total_users

    return months_activity


def get_app_deployment_info(domain, app_id):
    app = get_app(domain, app_id)
    domain_obj = Domain.get_by_name(domain)

    return (
        app.name,
        app.default_language,
        domain_obj.deployment.countries if domain_obj.deployment else []
    )


def generate_csv_report(months_activity):
    wb = Workbook()
    # Remove the default sheet created by openpyxl
    default_sheet = wb.active
    wb.remove(default_sheet)

    for month, activity_list in months_activity.items():
        ws = wb.create_sheet(title=month)
        ws.append(['Domain Name', 'Countries', 'App name', 'App ID', 'App default lang', 'Active User Count', 'Total Mobile Workers'])  # noqa E501
        for row in activity_list:
            ws.append([
                row.get('domain_name', ''),
                ', '.join(row.get('deployment_countries', '')),
                row.get('app_name', ''),
                row.get('app_id', ''),
                row.get('default_language', ''),
                row.get('user_count', 0),
                row.get('total_mobile_workers', 0)
            ])
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def send_email_report(csv_workbook, recipient_email):
    subject = "Worker Activity Report"
    body = "Please find attached the worker activity report."
    from_email = settings.DEFAULT_FROM_EMAIL
    to_emails = [recipient_email]

    email = EmailMessage(subject, body, from_email, to_emails)
    email.attach("worker_activity_report.xlsx", csv_workbook, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")  # noqa E501
    email.send()

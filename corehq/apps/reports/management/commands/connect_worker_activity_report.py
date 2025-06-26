from io import BytesIO
from openpyxl import Workbook

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


class Command(BaseCommand):
    help = """
    Generate a worker activity report for the given months.
    """

    def add_arguments(self, parser):
        parser.add_argument('--months', default=1, type=int, help="Last X months to evaluate")
        parser.add_argument('--limit', default=10, type=int, help="Grab the top X domains by user count")
        parser.add_argument('--recipient_email', type=str, help="Email address to send the report to")

    def handle(self, args, **options):
        months = options.get('months', 1)
        limit = options.get('limit', 10)
        recipient_email = options.get('recipient_email')

        if months > 12:
            # This is a safeguard to prevent excessive data collection
            self.stderr.write("Months cannot be greater than 12")
            return

        if not recipient_email:
            self.stderr.write("Please provide a recipient email using --recipient_email")
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

    # Get active users since start_date
    return (
        MALTRow.objects.filter(
            month__gte=start_date,
            num_of_forms__gte=1,
            domain_name__in=domain_names,
        )
        .values("user_id", "app_id")  # group by user and app
        .annotate(month_count=Count('month', distinct=True))  # noqa E501 count distinct months this user has a record for this app
        .filter(month_count=months)  # makes sure the user has activity for all months in the range
        .values("domain_name", "app_id")
        .annotate(user_count=Count("user_id", distinct=True))  # count distinct users for each app in the domain
        .order_by("-user_count")[:limit]  # sorted by user count and limited to the top results
    )


def augment_activity_results(months_activity):
    """Augment the activity data with total users per app on a domain."""
    print("Gathering total app users for each domain and app...")

    for _, activity_list in months_activity.items():
        for activity in activity_list:
            domain_name = activity.get('domain_name')
            app_id = activity.get('app_id')

            app_name, app_lang, domain_countries = get_app_deployment_info(domain_name, app_id)
            activity['app_name'] = app_name
            activity['default_language'] = app_lang
            activity['deployment_countries'] = domain_countries

            total_users = (
                MALTRow.objects.filter(
                    domain_name=domain_name,
                    app_id=app_id,
                )
                .values("user_id")
                .distinct()
                .count()
            )
            activity['total_app_users'] = total_users
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
        ws.append(['Domain Name', 'Countries', 'App name', 'App ID', 'App default lang', 'Active User Count', 'Total App Users'])  # noqa E501
        for row in activity_list:
            ws.append([
                row.get('domain_name', ''),
                row.get('deployment_countries', ''),
                row.get('app_name', ''),
                row.get('app_id', ''),
                row.get('default_language', ''),
                row.get('user_count', 0),
                row.get('total_app_users', 0)
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

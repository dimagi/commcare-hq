import calendar
import csv
import datetime
import io

from django.template.loader import render_to_string

from corehq.apps.accounting.models import DomainUserHistory
from corehq.apps.analytics.models import (
    PartnerAnalyticsReport,
    PartnerAnalyticsDataPoint,
    PartnerAnalyticsContact)
from corehq.apps.es import FormES
from corehq.apps.es.users import UserES
from corehq.apps.users.models import Invitation
from corehq.util.log import send_HTML_email
from dimagi.utils.dates import get_start_and_end_dates_of_month


NUMBER_OF_MOBILE_WORKERS = 'number_of_mobile_workers'
NUMBER_OF_SUBMISSIONS = 'number_of_submissions'
NUMBER_OF_WEB_USERS = 'number_of_web_users'

ACCESS_ODATA = 'access_odata'


def get_number_of_mobile_workers(domain, year, month):
    date_start, date_end = get_start_and_end_dates_of_month(year, month)
    domain_user_history = DomainUserHistory.objects.filter(
        domain=domain,
        record_date__gte=date_start,
        record_date__lte=date_end,
    )
    return (domain_user_history.first().num_users
            if domain_user_history.exists() else 0)


def get_number_of_submissions(domain, year, month):
    date_start, date_end = get_start_and_end_dates_of_month(year, month)
    return (
        FormES()
        .fields(['received_on'])
        .domain(domain)
        .submitted(
            gte=date_start,
            lt=date_end
        ).count()
    )


def get_number_of_web_users(domain, year, month):
    date_start, date_end = get_start_and_end_dates_of_month(year, month)
    users_existing_in_domain = set(
        doc['base_username']
        for doc in UserES().domain(domain)
        .web_users()
        .created(lte=date_end)
        .run().hits
    )
    users_who_accepted_invites = set(
        email
        for email in Invitation.objects.filter(
            domain=domain,
            is_accepted=True,
            invited_on__gte=date_start, invited_on__lt=date_end
        ).values_list('email', flat=True)
    )
    return len(users_existing_in_domain.union(users_who_accepted_invites))


def generate_monthly_mobile_worker_statistics(year, month):
    reports = PartnerAnalyticsReport.objects.filter(data_slug=NUMBER_OF_MOBILE_WORKERS)
    for report in reports:
        for domain in report.domains:
            PartnerAnalyticsDataPoint.objects.create(
                slug=NUMBER_OF_MOBILE_WORKERS,
                domain=domain,
                year=year,
                month=month,
                value=get_number_of_mobile_workers(domain, year, month)
            )


def generate_monthly_web_user_statistics(year, month):
    reports = PartnerAnalyticsReport.objects.filter(data_slug=NUMBER_OF_WEB_USERS)
    for report in reports:
        for domain in report.domains:
            PartnerAnalyticsDataPoint.objects.create(
                slug=NUMBER_OF_WEB_USERS,
                domain=domain,
                year=year,
                month=month,
                value=get_number_of_web_users(domain, year, month)
            )


def generate_monthly_submissions_statistics(year, month):
    reports = PartnerAnalyticsReport.objects.filter(data_slug=NUMBER_OF_SUBMISSIONS)
    for report in reports:
        for domain in report.domains:
            PartnerAnalyticsDataPoint.objects.create(
                slug=NUMBER_OF_SUBMISSIONS,
                domain=domain,
                year=year,
                month=month,
                value=get_number_of_submissions(domain, year, month)
            )


def track_partner_access(slug, domain):
    report = PartnerAnalyticsReport.objects.filter(
        domains__contains=[domain],
        data_slug=slug,
    )
    if report.exists():
        today = datetime.datetime.utcnow()
        data_point, _ = PartnerAnalyticsDataPoint.objects.get_or_create(
            slug=slug,
            domain=domain,
            year=today.year,
            month=today.month,
        )
        data_point.value = data_point.value + 1
        data_point.save()


def get_csv_details_for_partner(contact, year, month):
    headers = [
        "Title", "Project Space", "Value",
    ]
    body = []
    for report in PartnerAnalyticsReport.objects.filter(contact=contact):
        for domain in report.domains:
            data_point = PartnerAnalyticsDataPoint.objects.filter(
                slug=report.data_slug,
                domain=domain,
                year=year,
                month=month,
            )
            if data_point.exists():
                body.append([
                    report.title,
                    domain,
                    data_point.first().value,
                ])
    return headers, sorted(body)


def send_partner_emails(year, month):
    for contact in PartnerAnalyticsContact.objects.all():
        headers, body = get_csv_details_for_partner(contact, year, month)
        file_obj = io.StringIO()
        writer = csv.writer(file_obj)
        writer.writerow(headers)
        for row in body:
            writer.writerow([_get_csv_value(val) for val in row])
        filename = '{partner}_analytics_{year}_{month}'.format(
            partner=contact.organization_name,
            year=year,
            month=month,
        )
        context = {
            'month_name': calendar.month_name[month],
            'year': year,
        }
        send_HTML_email(
            "CommCare HQ Analytics Report: {partner} {month_name} {year}".format(
                partner=contact.organization_name,
                month_name=calendar.month_name[month],
                year=year,
            ),
            contact.emails,
            render_to_string("analytics/email/partner_analytics_report.html", context),
            text_content=render_to_string("analytics/email/partner_analytics_report.txt", context),
            file_attachments=[{'file_obj': file_obj, 'title': filename, 'mimetype': 'text/csv'}],
        )


def _get_csv_value(value):
    if isinstance(value, str):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        pass
    return str(value)

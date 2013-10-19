import datetime, logging

from celery.task import periodic_task
from celery.schedules import crontab
from django.conf import settings
from django.core.mail import send_mail

from dimagi.utils.web import get_url_base
from dimagi.utils.couch.database import get_db
from corehq.apps.groups.models import Group
from couchforms.models import XFormInstance

from .models import LegacyWeeklyReport
from .reports import LegacyReportView
from .constants import *


class Site(object):
    def __init__(self, group, date):
        self.name = group.name
        self.week = self.get_m_to_f(date)
        self.str_week = [str(d) for d in self.week]
        self.strategy = [0] * 5
        self.game = [0] * 5
        self.individual = {}
        self.emails = []
        for user in group.get_users():
            self.process_user(user)

    def get_m_to_f(self, date):
        """
        Returns a list whose elements are the dates of Monday - Friday
        for the most recent week to end prior to ``date``
        """
        iso = date.isoweekday()
        days_prior = iso - 5 if iso >= 5 else iso + 2
        friday = date - datetime.timedelta(days=days_prior)
        return [friday - datetime.timedelta(days=days)
                for days in range(4, -1, -1)]

    def process_user(self, user):
        for form in XFormInstance.get_forms_by_user(
                user, self.week[0], self.week[-1]):
            if form.xmlns == DAILY_DATA_XMLNS:
                username = form.metadata.username
                if username not in self.individual:
                    self.emails.append(user.email)
                    self.individual[username] = {
                        'strategy': [0] * 5,
                        'game': [0] * 5,
                    }
                self.process_form(form, username)
                # try:
                    # self.process_form(form, username)
                # except (KeyError, ValueError):
                    # pass

    def process_form(self, form, username):

        def get_or_0(obj, *args):
            val = obj
            for arg in args:
                try:
                    val = val[arg]
                except KeyError:
                    return 0
            return int(val)

        day = self.week.index(form.form['date_form_completed'])

        # test this out
        strategies = len(form.form.get('strategies_used').split())

        self.strategy[day] += strategies
        self.individual[username]['strategy'][day] += strategies

        games = get_or_0(form.form, 'game_questions', 'how_man_games')

        self.individual[username]['game'][day] += games
        self.game[day] += games

    # def process_form(self, form, username):
        # day = self.week.index(form.form['date_form_completed'])

        # strategies = len(form.form.get('strategies_used').split())
        # self.strategy[day] += strategies
        # self.individual[username]['strategy'][day] += strategies

        # raw_games = form.form['game_questions']['how_many_games']
        # games = int(raw_games) if raw_games else 0
        # self.individual[username]['game'][day] += games
        # self.game[day] += games


def save_report(date=None):
    """
    Save report for the most recent calendar week
    """
    if date is None:
        date = datetime.date.today()
    exclude = []
    for group in [g for g in Group.by_domain(DOMAIN) if g not in exclude]:
        site = Site(group, date)
        report = LegacyWeeklyReport(
            domain=DOMAIN,
            site=site.name,
            week_end_date=site.week[-1] + datetime.timedelta(days=1),
            site_strategy=site.strategy,
            site_game=site.game,
            individual=site.individual,
        )
        report.save()
        msg = "Saving legacy group %s to doc %s" % (group.name, report._id)
        logging.info(msg)
        
        # send an email to each site
        report_link = get_url_base() + LegacyReportView.get_url(DOMAIN)
        send_mail(
            "This week's Legacy report is available",
            "You can view your report here:\n{link}".format(link=report_link),
            settings.SERVER_EMAIL,
            site.emails
        )

def email():
    # send an email to each site
    report_link = get_url_base() + LegacyReportView.get_url(DOMAIN)
    send_mail(
        "This week's Legacy report is available",
        "You can view your report here:\n{link}".format(link=report_link),
        settings.SERVER_EMAIL,
        ['ethan@example.com']
    )

@periodic_task(run_every=crontab(hour=1, day_of_week=6),
        queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def run_report():
    save_report()

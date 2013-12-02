import datetime, logging

from celery.task import periodic_task
from celery.schedules import crontab
from django.conf import settings

from corehq.apps.groups.models import Group
from couchforms.models import XFormInstance

from .models import LegacyWeeklyReport
from .constants import *


class Site(object):
    def __init__(self, group, date):
        self.name = group.name
        self.week = self.get_m_to_f(date)
        self.strategy = [0] * 5
        self.game = [0] * 5
        self.individual = {}
        self.emails = []
        self.last_week = LegacyWeeklyReport.by_site(group,
                date=self.week[0] - datetime.timedelta(days=2))
        for user in group.get_users():
            self.process_user(user)
        try:
            self.weekly_totals = self.last_week.weekly_totals
        except (LookupError, AttributeError):
            self.weekly_totals = []
        self.weekly_totals.append(
            [self.week[0].strftime('%b %d'), sum([d for d in self.strategy if d>0])]
        )

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
        username = user.raw_username
        # initialize
        if username not in self.individual:
            self.emails.append(user.email)
            self.individual[username] = {
                'strategy': [0] * 5,
                'game': [0] * 5,
            }
        # process this week's forms
        for form in XFormInstance.get_forms_by_user(
                user, self.week[0], self.week[-1]):
            if form.xmlns == DAILY_DATA_XMLNS:
                self.process_form(form, username)
        # get and extend weekly totals
        try:
            weekly_totals = self.last_week.individual[username]['weekly_totals']
        except (LookupError, AttributeError):
            weekly_totals = []
        weekly_totals.append([
            self.week[0].strftime('%b %d'),
            sum([d for d in self.individual[username]['strategy'] if d>0])
        ])
        self.individual[username]['weekly_totals'] = weekly_totals


    def process_form(self, form, username):

        def get_or_None(obj, *args):
            val = obj
            for arg in args:
                try:
                    val = val[arg]
                except KeyError:
                    return None
            return val

        day = self.week.index(form.form['date_form_completed'])

        strategies = len(form.form.get('strategies_used').split())

        self.strategy[day] += strategies
        self.individual[username]['strategy'][day] += strategies

        games = int(get_or_None(form.form, 'game_questions', 'how_many_games') or 0)
        secret_game = get_or_None(form.form, 'game_questions', 'secret_game')
        games += 1 if secret_game == "yes" else 0

        self.individual[username]['game'][day] += games
        self.game[day] += games


def save_report(date=None):
    """
    Save report for the most recent calendar week
    """
    if date is None:
        date = datetime.date.today()

    for group in Group.by_domain(DOMAIN):
        site = Site(group, date)
        report = LegacyWeeklyReport(
            domain=DOMAIN,
            site=site.name,
            week_end_date=site.week[-1] + datetime.timedelta(days=1),
            site_strategy=site.strategy,
            site_game=site.game,
            individual=site.individual,
            weekly_totals=site.weekly_totals,
        )
        report.save()
        msg = "Saving legacy group %s to doc %s" % (group.name, report._id)
        logging.info(msg)


@periodic_task(
    run_every=crontab(hour=10, minute=1, day_of_week=6),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery')
)
def run_report():
    save_report()

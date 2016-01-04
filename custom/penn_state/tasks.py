import datetime, logging

from celery.task import periodic_task
from celery.schedules import crontab
from django.conf import settings

from corehq.apps.groups.models import Group
from corehq.apps.reports.util import make_form_couch_key
from couchforms.models import XFormInstance

from .models import LegacyWeeklyReport
from .constants import *


def get_m_to_f(date):
    """
    Returns a list whose elements are the dates of Monday - Friday
    for the most recent week to end prior to ``date``
    """
    iso = date.isoweekday()
    days_prior = iso - 5 if iso >= 5 else iso + 2
    friday = date - datetime.timedelta(days=days_prior)
    return [friday - datetime.timedelta(days=days)
            for days in range(4, -1, -1)]


all_days = 'monday tuesday wednesday thursday friday'

class Site(object):
    def __init__(self, group, date, on):
        self.name = group.name
        self.week = get_m_to_f(date)
        self.on = on
        self.strategy = self.schedule
        self.game = self.schedule
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

    @property
    def schedule(self):
        days = all_days.split(' ')
        schedule = []
        for d in days:
            schedule.append(0 if d in self.on else -1)
        return schedule

    def process_user(self, user):
        username = user.raw_username
        # initialize
        if username not in self.individual:
            self.emails.append(user.email)
            self.individual[username] = {
                'strategy': self.schedule,
                'game': self.schedule,
            }
        # process this week's forms
        key = make_form_couch_key(user.domain, user_id=user.user_id, xmlns=DAILY_DATA_XMLNS)
        forms = XFormInstance.view(
            "all_forms/view",
            startkey=key + [str(self.week[0])],
            endkey=key + [str(self.week[-1] + datetime.timedelta(days=1))],
            reduce=False,
            include_docs=True
        ).all()
        for form in forms:
            self.process_form(form, username)
        # get and extend weekly totals
        try:
            weekly_totals = self.last_week.individual[username]['weekly_totals']
        except (LookupError, AttributeError):
            weekly_totals = []
        weekly_totals.append([
            self.week[0].strftime(DATE_FORMAT),
            sum([d for d in self.individual[username]['strategy'] if d>0])
        ])
        self.individual[username]['weekly_totals'] = weekly_totals


    def process_form(self, form, username):
        try:
            day = self.week.index(form.form['date_form_completed'])
        except ValueError:
            msg = "Form %s created outside of report period. Ignoring." % form._id
            logging.info(msg)
            return

        def get_or_None(obj, *args):
            val = obj
            for arg in args:
                try:
                    val = val[arg]
                except KeyError:
                    return None
            return val

        strategies = len(form.form.get('strategies_used').split())

        self.strategy[day] += strategies
        self.individual[username]['strategy'][day] += strategies

        games = int(get_or_None(form.form, 'pax_games', 'game_questions', 'how_many_games') or 0)
        secret_game = get_or_None(form.form, 'game_questions', 'secret_game')
        games += 1 if secret_game == "yes" else 0

        self.individual[username]['game'][day] += games
        self.game[day] += games


def get_days_on(date):
    week = get_m_to_f(date)
    start = week[0] - datetime.timedelta(days=1)
    end = week[-1] + datetime.timedelta(days=1)
    forms = XFormInstance.view(
        'all_forms/view',
        startkey=['submission xmlns', DOMAIN, WEEKLY_SCHEDULE_XMLNS, start.isoformat()],
        endkey=['submission xmlns', DOMAIN, WEEKLY_SCHEDULE_XMLNS, end.isoformat()],
        reduce=False,
        include_docs=True,
    ).all()
    if forms:
        forms.sort(key=lambda form: form.received_on)
        return forms[-1].form


def save_report(date=None):
    """
    Save report for the most recent calendar week
    """
    if date is None:
        date = datetime.date.today()

    days_on = get_days_on(date)
    for group in Group.by_domain(DOMAIN):
        if group._id in GROUPS:
            s_id = GROUPS[group._id]['schedule_id']
            on = days_on.get(s_id, all_days) if days_on else all_days
            site = Site(group, date, on)
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

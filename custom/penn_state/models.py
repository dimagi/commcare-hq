import datetime

from couchdbkit.ext.django.schema import (Document, StringProperty,
    ListProperty, DictProperty, DateProperty)

from corehq.apps.groups.models import Group

from .constants import *

class LegacyWeeklyReport(Document):
    """
    This doc stores the aggregate weekly results per site.
    Example:
        domain: 'mikesproject',
        site: 'Pennsylvania State Elementary School',
        week_end_date: Saturday Sept 29, 2013,
        site_strategy: [3, -1, 0, 4, 2],
        site_game: [2, 4, 3, 1, 0],
        individual: {
            '123456': {
                'strategy': [2, 4, 0, 1, 3],
                'game': [1, 2, 4, 1, 0],
            },
        }
    Where each week is a 5 element list.  0 indicates that
    no strategies/games were recorded, -1 indicates an off
    day (nothing recorded, but that's okay).
    """
    domain = StringProperty()
    site = StringProperty()
    week_end_date = DateProperty()
    site_strategy = ListProperty()
    site_game = ListProperty()
    individual = DictProperty()

    @classmethod
    def by_user(cls, user, date=None):
        if date is None:
            date = {}

        # is there a better way to do this?
        group = Group.by_user('{}@{}.commcarehq.org'.format(user, DOMAIN))
        site = group.name

        # get the most recent saturday (isoweekday==6)
        days = [6, 7, 1, 2, 3, 4, 5]
        today = datetime.date.today()
        date = today - datetime.timedelta(days=days.index(today.isoweekday()))

        report = cls.view(
            'penn_state/smiley_weekly_reports',
            key=[DOMAIN, site, str(date)],
            reduce=False,
            include_docs=True,
        ).one()

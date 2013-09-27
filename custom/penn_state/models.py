import datetime

from couchdbkit.ext.django.schema import (Document, StringProperty,
    StringListProperty, IntegerProperty, ListProperty, DictProperty, DateProperty)

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
        """
        Returns a dict of results for a given individual.
        If a date is not supplied, return latest report.
        Example output:
        {
            'site_strategy': [3, -1, 0, 4, 2],     
            'site_game': [2, 4, 3, 1, 0],     
            'individual_strategy': [2, 4, 0, 1, 3],     
            'individual_game': [1, 2, 4, 1, 0],
        }
        """
        # site = get site from user

        # get the most recent saturday (isoweekly==6)
        days = [6, 7, 1, 2, 3, 4, 5]
        today = datetime.date.today()
        date = today - datetime.timedelta(days=days.index(today.isoweekday()))

        report = cls.view(
            'penn_state/smiley_weekly_reports',
            key=[DOMAIN, site, date],
            reduce=False,
            include_docs=True,
        ).one()

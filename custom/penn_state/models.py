import datetime

from dimagi.ext.couchdbkit import (Document, StringProperty,
    ListProperty, DictProperty, DateProperty)

from corehq.apps.groups.models import Group

from .constants import *


class LegacyWeeklyReport(Document):
    """
    This doc stores the aggregate weekly results per site.
    Example:
        domain: 'mikesproject',
        site: 'Pennsylvania State Elementary School',
        week_end_date: Saturday Sept 28, 2013,
        site_strategy: [3, -1, 0, 4, 2],
        site_game: [2, 4, 3, 1, 0],
        individual: {
            'mikeo': {
                'strategy': [2, 4, 0, 1, 3],
                'game': [1, 2, 4, 1, 0],
                'weekly_totals': [
                    ['Sept 9', 3],
                    ['Sept 16', 2],
                    ['Sept 23', 5],   # current week
                ],
            },
        },
        'weekly_totals': [
            ['Sept 9', 11],
            ['Sept 16', 6],
            ['Sept 23', 9],   # current week
        ],
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
    weekly_totals = ListProperty()

    @classmethod
    def by_site(cls, site, date=None):
        if isinstance(site, Group):
            site = site.name
        if date is None:
            # get the most recent saturday (isoweekday==6)
            days = [6, 7, 1, 2, 3, 4, 5]
            today = datetime.date.today()
            date = today - datetime.timedelta(
                days=days.index(today.isoweekday())
            )

        report = cls.view(
            'penn_state/smiley_weekly_reports',
            key=[DOMAIN, site, str(date)],
            reduce=False,
            include_docs=True,
        ).first()
        return report

    @classmethod
    def by_user(cls, user, date=None):
        # Users should only have one group, and it should be a report group
        groups = Group.by_user(user).all()
        # if len(groups) != 1 or not groups[0].reporting:
        if len(groups) == 0 or not groups[0].reporting:
            return

        site = groups[0].name
        return cls.by_site(site, date)


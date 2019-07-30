from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import datetime
from xml.etree.cElementTree import Element
from django.utils.translation import ugettext as _

from casexml.apps.phone.fixtures import FixtureProvider
from corehq.apps.calendar_fixture.models import CalendarFixtureSettings
from corehq.const import ONE_DAY
from corehq.toggles import CUSTOM_CALENDAR_FIXTURE


class CalendarFixtureProvider(FixtureProvider):
    id = 'enikshay:calendar'

    def __call__(self, restore_state):
        restore_user = restore_state.restore_user
        if not CUSTOM_CALENDAR_FIXTURE.enabled(restore_user.domain):
            return []

        # todo: for now just send down the current year. eventually this should be configurable and what not
        root_node = Element('fixture', {'id': self.id, 'user_id': restore_user.user_id})
        calendar_node = Element('calendar')
        root_node.append(calendar_node)
        current_day, end_date = get_calendar_range(restore_user.domain)
        last_day = current_day - datetime.timedelta(days=1)
        current_month_element = None
        current_year_element = None
        while current_day <= end_date:
            if current_year_element is None or current_day.year != last_day.year:
                current_year_element = Element('year', {'number': str(current_day.year)})
                calendar_node.append(current_year_element)
            if current_month_element is None or current_day.month != last_day.month:
                current_month_element = Element('month', {
                    'number': str(current_day.month),
                    'name': _(current_day.strftime('%B'))
                })
                current_year_element.append(current_month_element)

            current_day_element = Element('day', {
                'date': str(int(current_day.strftime('%s')) // (ONE_DAY)),  # mobile uses days since epoch
                'number': str(current_day.day),
                'name': _(current_day.strftime('%A')),
                'week': str(current_day.isocalendar()[1]),
            })
            current_month_element.append(current_day_element)
            last_day = current_day
            current_day += datetime.timedelta(days=1)

        return [root_node]


def get_calendar_range(domain):
    calendar_settings = CalendarFixtureSettings.for_domain(domain=domain)
    today = datetime.datetime.today()
    return (
        today - datetime.timedelta(days=calendar_settings.days_before),
        today + datetime.timedelta(days=calendar_settings.days_after),
    )


calendar_fixture_generator = CalendarFixtureProvider()

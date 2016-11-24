import datetime
from xml.etree.ElementTree import Element
from django.utils.translation import ugettext as _
from corehq.toggles import CUSTOM_CALENDAR_FIXTURE


class CalendarFixtureProvider(object):
    id = 'enikshay:calendar'

    def __call__(self, restore_user, version, last_sync=None, app=None):
        if not CUSTOM_CALENDAR_FIXTURE.enabled(restore_user.domain):
            return []

        # todo: for now just send down the current year. eventually this should be configurable and what not
        root_node = Element('fixture', {'id': self.id, 'user_id': restore_user.user_id})
        calendar_node = Element('calendar')
        root_node.append(calendar_node)
        current_day = _get_calendar_start_date(restore_user.domain)
        end_date = _get_calendar_end_date(restore_user.domain)
        last_day = current_day - datetime.timedelta(days=1)
        while current_day < end_date:
            if current_day.year != last_day.year:
                current_year_element = Element('year', {'number': str(current_day.year)})
                calendar_node.append(current_year_element)
            if current_day.month != last_day.month:
                current_month_element = Element('month', {
                    'number': str(current_day.month),
                    'name': _(current_day.strftime('%B'))
                })
                current_year_element.append(current_month_element)

            current_day_element = Element('day', {
                'date': str(int(current_day.strftime('%s')) / (60 * 60 * 24)),  # mobile uses days since epoch
                'number': str(current_day.day),
                'name': _(current_day.strftime('%A')),
                'week': str(current_day.isocalendar()[1]),
            })
            current_month_element.append(current_day_element)
            last_day = current_day
            current_day += datetime.timedelta(days=1)

        return [root_node]


def _get_calendar_start_date(domain):
    return datetime.date(datetime.datetime.now().year, 1, 1)


def _get_calendar_end_date(domain):
    return datetime.date(datetime.datetime.now().year + 1, 1, 1)


calendar_fixture_generator = CalendarFixtureProvider()

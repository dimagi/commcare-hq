import calendar
import datetime
from collections import namedtuple

from couchdbkit.exceptions import BadValueError
from dimagi.ext.couchdbkit import (
    DocumentSchema,
    FloatProperty,
    IntegerProperty,
    StringListProperty,
    StringProperty,
)
from dimagi.utils.dates import DateSpan
from django.utils.translation import gettext as _

from corehq.apps.app_manager import const
from corehq.apps.reports.daterange import (
    get_daterange_start_end_dates,
    get_simple_dateranges,
)
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_domain


class ReportAppFilter(DocumentSchema):

    @classmethod
    def wrap(cls, data):
        if cls is ReportAppFilter:
            return get_report_filter_class_for_doc_type(data['doc_type']).wrap(data)
        else:
            return super(ReportAppFilter, cls).wrap(data)

    def get_filter_value(self, user, ui_filter):
        raise NotImplementedError


MobileFilterConfig = namedtuple('MobileFilterConfig', ['doc_type', 'filter_class', 'short_description'])


def get_all_mobile_filter_configs():
    return [
        MobileFilterConfig('AutoFilter', AutoFilter, _('Value equal to a standard user property')),
        MobileFilterConfig('CustomDataAutoFilter', CustomDataAutoFilter,
                           _('Value equal to a custom user property')),
        MobileFilterConfig('StaticChoiceFilter', StaticChoiceFilter, _('An exact match of a constant value')),
        MobileFilterConfig('StaticChoiceListFilter', StaticChoiceListFilter,
                           _('An exact match of a dynamic property')),
        MobileFilterConfig('StaticDatespanFilter', StaticDatespanFilter, _('A standard date range')),
        MobileFilterConfig('CustomDatespanFilter', CustomDatespanFilter, _('A custom range relative to today')),
        MobileFilterConfig('CustomMonthFilter', CustomMonthFilter,
                           _("Custom Month Filter (you probably don't want this)")),
        MobileFilterConfig('MobileSelectFilter', MobileSelectFilter, _('Show choices on mobile device')),
        MobileFilterConfig('AncestorLocationTypeFilter', AncestorLocationTypeFilter,
                           _("Ancestor location of the user's assigned location of a particular type")),
        MobileFilterConfig('NumericFilter', NumericFilter, _('A numeric expression')),
    ]


def get_report_filter_class_for_doc_type(doc_type):
    matched_configs = [config for config in get_all_mobile_filter_configs() if config.doc_type == doc_type]
    if not matched_configs:
        raise ValueError('Unexpected doc_type for ReportAppFilter', doc_type)
    else:
        assert len(matched_configs) == 1
        return matched_configs[0].filter_class


def _filter_by_case_sharing_group_id(user, ui_filter):
    from corehq.apps.reports_core.filters import Choice
    return [
        Choice(value=group._id, display=None)
        for group in user.get_case_sharing_groups()
    ]


def _filter_by_location_id(user, ui_filter):
    return ui_filter.value(**{ui_filter.name: user.location_id,
                              'request_user': user})


def _filter_by_location_ids(user, ui_filter):
    from corehq.apps.userreports.reports.filters.values import CHOICE_DELIMITER
    return ui_filter.value(**{ui_filter.name: CHOICE_DELIMITER.join(user.assigned_location_ids),
                              'request_user': user})


def _filter_by_username(user, ui_filter):
    from corehq.apps.reports_core.filters import Choice
    return Choice(value=user.raw_username, display=None)


def _filter_by_user_id(user, ui_filter):
    from corehq.apps.reports_core.filters import Choice
    return Choice(value=user._id, display=None)


def _filter_by_parent_location_id(user, ui_filter):
    location = user.sql_location
    location_parent = location.parent.location_id if location and location.parent else None
    return ui_filter.value(**{ui_filter.name: location_parent,
                              'request_user': user})


AutoFilterConfig = namedtuple('AutoFilterConfig', ['slug', 'filter_function', 'short_description'])


def get_auto_filter_configurations():
    return [
        AutoFilterConfig('case_sharing_group', _filter_by_case_sharing_group_id,
                         _("The user's case sharing group (filter must be of choice_provider type)")),
        AutoFilterConfig('location_id', _filter_by_location_id, _("The user's assigned location")),
        AutoFilterConfig('location_ids', _filter_by_location_ids, _("All of the user's assigned locations")),
        AutoFilterConfig('parent_location_id', _filter_by_parent_location_id,
                         _("The parent location of the user's assigned location")),
        AutoFilterConfig('username', _filter_by_username, _("The user's username")),
        AutoFilterConfig('user_id', _filter_by_user_id, _("The user's ID")),
    ]


def _get_auto_filter_function(slug):
    matched_configs = [config for config in get_auto_filter_configurations() if config.slug == slug]
    if not matched_configs:
        raise ValueError('Unexpected ID for AutoFilter', slug)
    else:
        assert len(matched_configs) == 1
        return matched_configs[0].filter_function


class AutoFilter(ReportAppFilter):
    filter_type = StringProperty(choices=[f.slug for f in get_auto_filter_configurations()])

    def get_filter_value(self, user, ui_filter):
        return _get_auto_filter_function(self.filter_type)(user, ui_filter)


class CustomDataAutoFilter(ReportAppFilter):
    custom_data_property = StringProperty()

    def get_filter_value(self, user, ui_filter):
        from corehq.apps.reports_core.filters import Choice
        user_data = user.get_user_data(getattr(user, 'current_domain', user.domain))
        return Choice(value=user_data[self.custom_data_property], display=None)


class StaticChoiceFilter(ReportAppFilter):
    select_value = StringProperty()

    def get_filter_value(self, user, ui_filter):
        from corehq.apps.reports_core.filters import Choice
        return [Choice(value=self.select_value, display=None)]


class StaticChoiceListFilter(ReportAppFilter):
    value = StringListProperty()

    def get_filter_value(self, user, ui_filter):
        from corehq.apps.reports_core.filters import Choice
        return [Choice(value=string_value, display=None) for string_value in self.value]


class StaticDatespanFilter(ReportAppFilter):
    date_range = StringProperty(
        choices=[choice.slug for choice in get_simple_dateranges()],
        required=True,
    )

    def get_filter_value(self, user, ui_filter):
        start_date, end_date = get_daterange_start_end_dates(self.date_range)
        return DateSpan(startdate=start_date, enddate=end_date)


class CustomDatespanFilter(ReportAppFilter):
    operator = StringProperty(
        choices=[
            '=',
            '<=',
            '>=',
            '>',
            '<',
            'between'
        ],
        required=True,
    )
    date_number = StringProperty(required=True)
    date_number2 = StringProperty()

    def get_filter_value(self, user, ui_filter):
        assert user is not None, (
            "CustomDatespanFilter.get_filter_value must be called "
            "with an OTARestoreUser object, not None")

        timezone = get_timezone_for_domain(user.domain)
        today = ServerTime(datetime.datetime.utcnow()).user_time(timezone).done().date()
        start_date = end_date = None
        days = int(self.date_number)
        if self.operator == 'between':
            days2 = int(self.date_number2)
            # allows user to have specified the two numbers in either order
            if days > days2:
                end = days2
                start = days
            else:
                start = days2
                end = days
            start_date = today - datetime.timedelta(days=start)
            end_date = today - datetime.timedelta(days=end)
        elif self.operator == '=':
            start_date = end_date = today - datetime.timedelta(days=days)
        elif self.operator == '>=':
            start_date = None
            end_date = today - datetime.timedelta(days=days)
        elif self.operator == '<=':
            start_date = today - datetime.timedelta(days=days)
            end_date = None
        elif self.operator == '<':
            start_date = today - datetime.timedelta(days=days - 1)
            end_date = None
        elif self.operator == '>':
            start_date = None
            end_date = today - datetime.timedelta(days=days + 1)
        return DateSpan(startdate=start_date, enddate=end_date)


def is_lte(integer):
    def validate(x):
        if not x <= integer:
            raise BadValueError('Value must be less than or equal to {}'.format(integer))
    return validate


def is_gte(integer):
    def validate(x):
        if not x >= integer:
            raise BadValueError('Value must be greater than or equal to {}'.format(integer))
    return validate


class CustomMonthFilter(ReportAppFilter):
    """
    Filter by months that start on a day number other than 1

    See [FB 215656](http://manage.dimagi.com/default.asp?215656)
    """
    # Values for start_of_month < 1 specify the number of days from the end of the month. Values capped at
    # len(February).
    start_of_month = IntegerProperty(
        required=True,
        validators=(is_gte(-27), is_lte(28))
    )
    # DateSpan to return i.t.o. number of months to go back
    period = IntegerProperty(
        default=const.DEFAULT_MONTH_FILTER_PERIOD_LENGTH,
        validators=(is_gte(0),)
    )

    @classmethod
    def wrap(cls, doc):
        doc['start_of_month'] = int(doc['start_of_month'])
        if 'period' in doc:
            doc['period'] = int(doc['period'] or const.DEFAULT_MONTH_FILTER_PERIOD_LENGTH)
        return super(CustomMonthFilter, cls).wrap(doc)

    def get_filter_value(self, user, ui_filter):
        def get_last_month(this_month):
            return datetime.date(this_month.year, this_month.month, 1) - datetime.timedelta(days=1)

        def get_last_day(date):
            _, last_day = calendar.monthrange(date.year, date.month)
            return last_day

        start_of_month = int(self.start_of_month)
        today = datetime.date.today()
        if start_of_month > 0:
            start_day = start_of_month
        else:
            # start_of_month is zero or negative. Work backwards from the end of the month
            start_day = get_last_day(today) + start_of_month

        # Loop over months backwards for period > 0
        month = today if today.day >= start_day else get_last_month(today)
        for i in range(int(self.period)):
            month = get_last_month(month)

        if start_of_month > 0:
            start_date = datetime.date(month.year, month.month, start_day)
            days = get_last_day(start_date) - 1
            end_date = start_date + datetime.timedelta(days=days)
        else:
            start_day = get_last_day(month) + start_of_month
            start_date = datetime.date(month.year, month.month, start_day)
            next_month = datetime.date(month.year, month.month, get_last_day(month)) + datetime.timedelta(days=1)
            end_day = get_last_day(next_month) + start_of_month - 1
            end_date = datetime.date(next_month.year, next_month.month, end_day)

        return DateSpan(startdate=start_date, enddate=end_date)


class MobileSelectFilter(ReportAppFilter):

    def get_filter_value(self, user, ui_filter):
        return None


class AncestorLocationTypeFilter(ReportAppFilter):
    ancestor_location_type_name = StringProperty()

    def get_filter_value(self, user, ui_filter):
        from corehq.apps.locations.models import SQLLocation
        from corehq.apps.reports_core.filters import REQUEST_USER_KEY

        kwargs = {REQUEST_USER_KEY: user}
        try:
            ancestor = user.sql_location.get_ancestors(include_self=True).\
                get(location_type__name=self.ancestor_location_type_name)
            kwargs[ui_filter.name] = ancestor.location_id
        except (AttributeError, SQLLocation.DoesNotExist):
            # user.sql_location is None, or location does not have an ancestor of that type
            pass

        return ui_filter.value(**kwargs)


class NumericFilter(ReportAppFilter):
    operator = StringProperty(choices=['=', '!=', '<', '<=', '>', '>=']),
    operand = FloatProperty()

    @classmethod
    def wrap(cls, doc):
        doc['operand'] = float(doc['operand'])
        return super(NumericFilter, cls).wrap(doc)

    def get_filter_value(self, user, ui_filter):
        return {
            'operator': self.operator,
            'operand': self.operand,
        }

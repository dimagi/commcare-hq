from xml.etree import ElementTree
from datetime import datetime
import pytz
from corehq.apps.callcenter.indicator_sets import CallCenterIndicators
from corehq.apps.users.models import CommCareUser
from corehq.util.soft_assert import soft_assert
from corehq.util.timezones.conversions import UserTime, ServerTime
from dimagi.utils.logging import notify_exception

utc = pytz.utc


def should_sync(domain, last_sync, utcnow=None):
    # definitely sync if we haven't synced before
    if not last_sync or not last_sync.date:
        return True

    # utcnow only used in tests to mock other times
    utcnow = utcnow or datetime.utcnow()

    try:
        timezone = domain.get_default_timezone()
    except pytz.UnknownTimeZoneError:
        timezone = utc

    _assert = soft_assert(to=['droberts' + '@' + 'dimagi.com'])

    last_sync_utc = last_sync.date

    if not _assert(last_sync_utc.tzinfo is None,
                   'last_sync.date should be an offset-naive dt'):
        last_sync_utc = UserTime(last_sync_utc).server_time().done()

    # check if user has already synced today (in local timezone).
    # Indicators only change daily.
    last_sync_local = ServerTime(last_sync_utc).user_time(timezone).done()
    current_date_local = ServerTime(utcnow).user_time(timezone).done()

    if current_date_local.date() != last_sync_local.date():
        return True

    return False


class IndicatorsFixturesProvider(object):
    id = 'indicators'

    def __call__(self, user, version, last_sync=None, app=None):
        assert isinstance(user, CommCareUser)

        domain = user.project
        fixtures = []

        if self._should_return_no_fixtures(domain, last_sync):
            return fixtures

        try:
            fixtures.append(gen_fixture(user, CallCenterIndicators(
                domain.name,
                domain.default_timezone,
                domain.call_center_config.case_type,
                user
            )))
        except Exception:  # blanket exception catching intended
            notify_exception(None, 'problem generating callcenter fixture', details={
                'user_id': user._id,
                'domain': user.domain
            })

        return fixtures

    @staticmethod
    def _should_return_no_fixtures(domain, last_sync):
        config = domain.call_center_config
        return (
            not domain or
            not (config.fixtures_are_active() and config.config_is_valid()) or
            not should_sync(domain, last_sync)
        )

indicators_fixture_generator = IndicatorsFixturesProvider()


def gen_fixture(user, indicator_set):
    """
    Generate the fixture from the indicator data.

    :param user: The user.
    :param indicator_set: A subclass of SqlIndicatorSet
    """
    """
    Example output:

    indicator_set.name = 'demo'
    indicator_set.get_data() = {'user_case1': {'indicator_a': 1, 'indicator_b': 2}}

    <fixture id="indicators:demo" user_id="...">
        <indicators>
            <case id="user_case1">
                <indicator_a>1</indicator_a>
                <indicator_b>2</indicator_2>
            </case>
        </indicators>
    </fixture>
    """
    name = indicator_set.name
    data = indicator_set.get_data()

    fixture = ElementTree.Element('fixture', attrib={
        'id': ':'.join((IndicatorsFixturesProvider.id, name)),
        'user_id': user.user_id,
        'date': indicator_set.reference_date.isoformat()
    })
    indicators_node = ElementTree.SubElement(fixture, 'indicators')
    for case_id, indicators in data.iteritems():
        group = ElementTree.SubElement(indicators_node, 'case', attrib={'id': case_id})
        for name, value in indicators.items():
            indicator = ElementTree.SubElement(group, name)
            indicator.text = str(value)

    return fixture

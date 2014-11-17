from xml.etree import ElementTree
from datetime import datetime
import pytz
from corehq.apps.callcenter.indicator_sets import CallCenterIndicators
from corehq.apps.users.models import CommCareUser
from dimagi.utils.logging import notify_exception

utc = pytz.utc


def should_sync(domain, last_sync, utcnow=None):
    # definitely sync if we haven't synced before
    if not last_sync or not last_sync.date:
        return True

    try:
        timezone = pytz.timezone(domain.default_timezone)
    except pytz.UnknownTimeZoneError:
        timezone = utc

    # check if user has already synced today (in local timezone). Indicators only change daily.
    last_sync_utc = last_sync.date if last_sync.date.tzinfo else utc.localize(last_sync.date)
    last_sync_local = timezone.normalize(last_sync_utc.astimezone(timezone))

    utcnow = utcnow if utcnow else utc.localize(datetime.utcnow())
    current_date_local = timezone.normalize(utcnow.astimezone(timezone))

    if current_date_local.date() != last_sync_local.date():
        return True

    return False


def indicators_fixture_generator(user, version, case_sync_op=None, last_sync=None):
    assert isinstance(user, CommCareUser)

    domain = user.project
    fixtures = []

    if not domain or not (hasattr(domain, 'call_center_config') and domain.call_center_config.enabled):
        return fixtures

    if not should_sync(domain, last_sync):
        return fixtures

    try:
        fixtures.append(gen_fixture(user, CallCenterIndicators(domain, user, case_sync_op=case_sync_op)))
    except Exception:  # blanket exception catching intended
        notify_exception(None, 'problem generating callcenter fixture', details={
            'user_id': user._id,
            'domain': user.domain
        })

    return fixtures


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
        'id': 'indicators:%s' % name,
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

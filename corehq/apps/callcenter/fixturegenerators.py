import logging
from xml.etree import ElementTree
from corehq.apps.callcenter.indicator_sets import CallCenterIndicators
from corehq.apps.users.models import CommCareUser


logger = logging.getLogger(__name__)


def indicators(user, version, last_sync):
    assert isinstance(user, CommCareUser)
    fixtures = []
    domain = user.project
    if domain and hasattr(domain, 'call_center_config') and domain.call_center_config.enabled:
        try:
            fixtures.append(gen_fixture(user, CallCenterIndicators(domain, user)))
        except Exception as e:  # blanket exception catching intended
            logger.exception('problem generating callcenter fixture for user {user}: {msg}'.format(
                user=user._id, msg=str(e)))

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

    fixture = ElementTree.Element('fixture', attrib={'id': 'indicators:%s' % name, 'user_id': user.user_id})
    indicators_node = ElementTree.SubElement(fixture, 'indicators')
    for case_id, indicators in data.iteritems():
        group = ElementTree.SubElement(indicators_node, 'case', attrib={'id': case_id})
        for name, value in indicators.items():
            indicator = ElementTree.SubElement(group, name)
            indicator.text = str(value)

    return fixture

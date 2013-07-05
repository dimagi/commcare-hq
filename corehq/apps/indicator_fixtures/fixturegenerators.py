from xml.etree import ElementTree
from casexml.apps.case.xml import V2
from corehq.apps.indicator_fixtures.indicator_sets import CallCenter
from corehq.apps.users.models import CommCareUser


def indicators(user, version=V2, last_sync=None):
    if isinstance(user, CommCareUser):
        pass
    elif hasattr(user, "_hq_user") and user._hq_user is not None:
        user = user._hq_user
    else:
        return []

    cc = CallCenter()

    return gen_fixture(user, cc.name, cc.group, cc.data)


def gen_fixture(user, name, group, data):
    """
    Generate the fixture from the indicator data.

    :param name: the name of the indicator set
    :param group: the name of the group_by field or None
    :param data: the indicator set data

    e.g.
    name = 'demo'
    group = None
    data = {'indicator_a': 1}
    <fixture id="indicators:demo" user_id="...">
        <indicators>
            <indicator_a>1</indicator_a>
        </indicators>
    </fixture>

    name = 'demo'
    group = 'user'
    data = {'user1': {'indicator_a': 1}}
    <fixture id="indicators:demo" user_id="...">
        <indicators>
            <user id="user1">
                <indicator_a>1</indicator_a>
            </user>
        </indicators>
    </fixture>
    """

    xFixture = ElementTree.Element('fixture', attrib={'id': 'indicators:%s' % name, 'user_id': user.user_id})
    xIndicators = ElementTree.SubElement(xFixture, 'indicators')
    if group:
        for group_id, group_data in data.items():
            xGroup = ElementTree.SubElement(xIndicators, group, attrib={'id': group_id})
            for k, v in group_data.items():
                if not k == group:
                    xIndicator = ElementTree.SubElement(xGroup, k)
                    xIndicator.text = v
    else:
        for k, v in data.items():
            xIndicator = ElementTree.SubElement(xIndicators, k)
            xIndicator.text = v

    return xFixture

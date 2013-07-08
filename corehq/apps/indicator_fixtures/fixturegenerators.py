from xml.etree import ElementTree
from casexml.apps.case.xml import V2
from corehq.apps.users.models import CommCareUser


def indicators(user, version=V2, last_sync=None):
    if isinstance(user, CommCareUser):
        pass
    elif hasattr(user, "_hq_user") and user._hq_user is not None:
        user = user._hq_user
    else:
        return []

    # TODO: get indicator sets for user
    indicator_sets = []
    fixtures = []
    for set in indicator_sets:
        fixtures.append(gen_fixture(user, set))

    return fixtures


def gen_fixture(user, indicator_set, include_empty=True):
    """
    Generate the fixture from the indicator data.

    :param user: The user.
    :param indicator_set: A subclass of SqlIndicatorSet
    :param include_empty: True to include indicators that have no value for the current time period.
    """
    """
    name = 'demo'
    group = None
    data = {'indicator_a': 1}
    indicator_names = ['indicator_a', 'indicator_b']
    <fixture id="indicators:demo" user_id="...">
        <indicators>
            <indicator_a>1</indicator_a>
            <indicator_b>0</indicator_b>
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
    name = indicator_set.name
    group = indicator_set.group_by
    data = indicator_set.data
    indicator_names = None
    if include_empty:
        indicator_names = [c.name for c in indicator_set.actual_columns]

    xFixture = ElementTree.Element('fixture', attrib={'id': 'indicators:%s' % name, 'user_id': user.user_id})
    xIndicators = ElementTree.SubElement(xFixture, 'indicators')
    if group:
        for group_id, group_data in data.items():
            xGroup = ElementTree.SubElement(xIndicators, group, attrib={'id': group_id})
            if not indicator_names:
                indicator_names = group_data.keys()

            for i in indicator_names:
                if not i == group:
                    xIndicator = ElementTree.SubElement(xGroup, i)
                    xIndicator.text = str(group_data.get(i, 0))
    else:
        if not indicator_names:
            indicator_names = data.keys()
        for i in indicator_names:
            xIndicator = ElementTree.SubElement(xIndicators, i)
            xIndicator.text = str(data.get(i, 0))

    return xFixture

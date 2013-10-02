from xml.etree import ElementTree
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from custom.bihar.reports.indicators.indicators import IndicatorDataProvider, IndicatorConfig, INDICATOR_SETS

# meh
hard_coded_domains = ('care-bihar', 'bihar')
hard_coded_indicators = 'homevisit'
hard_coded_group_filter = lambda group: bool(group.metadata.get('awc-code', False))
hard_coded_fixture_id = 'indicators:bihar-supervisor'

def generator(user, *args, **kwargs):
    # todo: this appears in the beginning of all fixture generators. should fix
    if isinstance(user, CommCareUser):
        pass
    elif hasattr(user, "_hq_user") and user._hq_user is not None:
        user = user._hq_user
    else:
        return []

    if user.domain in hard_coded_domains:
        groups = filter(hard_coded_group_filter, Group.by_user(user))
        if len(groups) == 1:
            data_provider = IndicatorDataProvider(
                domain=user.domain,
                indicator_set=IndicatorConfig(INDICATOR_SETS).get_indicator_set(hard_coded_indicators),
                groups=groups,
            )
            fixture_provider = IndicatorFixtureProvider(
                hard_coded_fixture_id, user, data_provider
            )
            return [fixture_provider.to_fixture()]
    return []

class IndicatorFixtureProvider(object):

    def __init__(self, id, user, data_provider):
        self.id = id
        self.user = user
        self.data_provider = data_provider

    def to_fixture(self):
        """
        Generate a fixture representation of the indicator set. Something like the following:
           <fixture id="indicators:bihar-supervisor" user_id="3ce8b1611c38e956d3b3b84dd3a7ac18">
              <group id="1012aef098ab0c0" team="Samda Team 1">
                 <indicators>
                    <indicator id="bp">
                       <name>BP Visits last 30 days</name>
                       <done>25</done>
                       <due>22</due>
                       <clients>
                          <client id="a1029b09c090s9d173"></client>
                          <client id="bad7a1029b09c090s9"></client>
                       </clients>
                    </indicator>
                 </indicators>
              </group>
           </fixture>
        """
        def _el(tag, text):
            el = ElementTree.Element(tag)
            el.text = unicode(text)
            return el

        def _indicator_to_fixture(indicator):
            ind_el = ElementTree.Element('indicator',
                attrib={
                    'id': indicator.slug,
                },
            )
            done, due = self.data_provider.get_indicator_data(indicator)
            ind_el.append(_el('name', indicator.name))
            ind_el.append(_el('done', done))
            ind_el.append(_el('due', due))
            clients = ElementTree.Element('clients')
            for case_id in self.data_provider.get_case_ids(indicator):
                client = ElementTree.Element('client',
                    attrib={
                        'id': case_id,
                    }

                )
                clients.append(client)
            ind_el.append(clients)
            return ind_el

        root = ElementTree.Element('fixture',
            attrib={'id': self.id, 'user_id': self.user._id},
        )
        group = ElementTree.Element('group',
            attrib={
                'id': self.data_provider.groups[0]._id,
                'team': self.data_provider.groups[0].name
            },
        )
        root.append(group)
        indicators = ElementTree.Element('indicators')
        for indicator in self.data_provider.summary_indicators:
            indicators.append(_indicator_to_fixture(indicator))
        group.append(indicators)
        return root

    def to_string(self):
        return ElementTree.tostring(self.to_fixture(), encoding="utf-8")



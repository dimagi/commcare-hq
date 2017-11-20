from __future__ import absolute_import
from xml.etree import cElementTree as ElementTree
from django.utils.translation import ugettext as _

from casexml.apps.phone.fixtures import FixtureProvider
from corehq.util.translation import localize
from custom.bihar import BIHAR_DOMAINS
from custom.bihar.reports.indicators.indicators import IndicatorDataProvider, IndicatorConfig, INDICATOR_SETS
import six

# meh
hard_coded_domains = BIHAR_DOMAINS
hard_coded_indicators = 'homevisit'
hard_coded_group_filter = lambda group: bool((group.metadata or {}).get('awc-code', False))
hard_coded_fixture_id = 'indicators:bihar-supervisor'


class IndicatorFixtureProvider(FixtureProvider):
    id = hard_coded_fixture_id

    def __call__(self, restore_state):
        restore_user = restore_state.restore_user

        if restore_user.domain in hard_coded_domains:
            groups = filter(hard_coded_group_filter, restore_user.get_groups())
            if len(groups) == 1:
                data_provider = IndicatorDataProvider(
                    domain=restore_user.domain,
                    indicator_set=IndicatorConfig(INDICATOR_SETS).get_indicator_set(hard_coded_indicators),
                    groups=groups,
                )
                return [self.get_fixture(restore_user.user_id, data_provider)]
        return []

    def get_fixture(self, restore_user_id, data_provider):
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
                          <client id="a1029b09c090s9d173" status="done"></client>
                          <client id="bad7a1029b09c090s9" status="due"></client>
                       </clients>
                    </indicator>
                 </indicators>
              </group>
           </fixture>
        """
        def _el(tag, text, _attrib=None):
            el = ElementTree.Element(tag, _attrib or {})
            el.text = six.text_type(text)
            return el

        def _indicator_to_fixture(indicator):
            ind_el = ElementTree.Element('indicator',
                {
                    'id': indicator.slug,
                },
            )
            done, due = data_provider.get_indicator_data(indicator)
            ind_el.append(_el('name', indicator.name, {'lang': 'en'}))
            ind_el.append(_el('name', _(indicator.name), {'lang': 'hin'}))
            ind_el.append(_el('done', done))
            ind_el.append(_el('due', due))
            clients = ElementTree.Element('clients')
            for case_id, data in data_provider.get_case_data(indicator).items():
                client = ElementTree.Element('client',
                    {
                        'id': case_id,
                        'status': 'done' if data['num'] else 'due',
                    }

                )
                clients.append(client)
            ind_el.append(clients)
            return ind_el

        # switch to hindi so we can use our builtin translations
        with localize('hin'):
            root = ElementTree.Element('fixture',
                {'id': self.id, 'user_id': restore_user_id},
            )
            group = ElementTree.Element('group',
                {
                    'id': data_provider.groups[0]._id,
                    'team': data_provider.groups[0].name
                },
            )
            root.append(group)
            indicators = ElementTree.Element('indicators')

            # hack: we have to have something with 'clients' show up first in the list
            # context: http://manage.dimagi.com/default.asp?107569
            sorted_indicators = sorted(data_provider.summary_indicators,
                                       key=lambda indicator: -len(data_provider.get_case_data(indicator)))
            for indicator in sorted_indicators:
                indicators.append(_indicator_to_fixture(indicator))
            group.append(indicators)
            return root

generator = IndicatorFixtureProvider()

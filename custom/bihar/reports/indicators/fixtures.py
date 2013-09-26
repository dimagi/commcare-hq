from xml.etree import ElementTree


class IndicatorFixtureProvider(object):

    def __init__(self, id, user_id, data_provider):
        self.id = id
        self.user_id = user_id
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
            attrib={'id': self.id, 'user_id': self.user_id},
        )
        group = ElementTree.Element('group',
            attrib={
                'id': self.data_provider.group._id,
                'team': self.data_provider.group.name
            },
        )
        root.append(group)
        indicators = ElementTree.Element('indicators')
        for indicator in self.data_provider.summary_indicators:
            indicators.append(_indicator_to_fixture(indicator))
        group.append(indicators)
        return ElementTree.tostring(root, encoding="utf-8")



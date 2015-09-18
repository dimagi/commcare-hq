from corehq.apps.app_manager.suite_xml.basic import SectionSuiteContributor
from corehq.apps.app_manager.suite_xml.xml import Fixture
from lxml import etree


class FixtureContributor(SectionSuiteContributor):
    section = 'fixtures'
    
    def get_section_contributions(self):
        if self.app.case_sharing:
            f = Fixture(id='user-groups')
            f.user_id = 'demo_user'
            groups = etree.fromstring("""
                <groups>
                    <group id="demo_user_group_id">
                        <name>Demo Group</name>
                    </group>
                </groups>
            """)
            f.set_content(groups)
            yield f

"""
FixtureContributor
------------------

This contributor adds a tiny fixture with a demo user group.

It's also the parent class for ``SchedulerFixtureContributor``, a flagged feature.
"""
from lxml import etree

from corehq.apps.app_manager.suite_xml.contributors import SectionContributor
from corehq.apps.app_manager.suite_xml.xml_models import Fixture
from corehq.util.timer import time_method


class FixtureContributor(SectionContributor):
    section_name = 'fixtures'

    @time_method()
    def get_section_elements(self):
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

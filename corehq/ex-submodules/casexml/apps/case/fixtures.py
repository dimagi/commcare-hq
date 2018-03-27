from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.case.xml.generator import safe_element
from casexml.apps.phone.xml import get_casedb_element
from xml.etree import cElementTree as ElementTree


class CaseDBFixture(object):
    """Used to provide a casedb-like structure as a fixture

    Does not follow the standard FixtureGenerator pattern since it is currently
    not used during a regular sync operation, and is user-agnostic
    """

    id = "case"

    def __init__(self, cases):
        if not isinstance(cases, list):
            self.cases = [cases]
        else:
            self.cases = cases

    @property
    def fixture(self):
        """For a list of cases, return a fixture with all case properties

        <results id="case">
            <case case_id="" case_type="" owner_id="" status="">
                <case_name/>
                <date_opened/>
                <last_modified/>
                <case_property />
                <index>
                    <a12345 case_type="" relationship="" />
                </index>
                <attachment>
                    <a12345 />
                </attachment>
            </case>
            <case>
            ...
            </case>
        </results>

        https://github.com/dimagi/commcare/wiki/casedb
        https://github.com/dimagi/commcare/wiki/fixtures
        """
        element = safe_element("results")
        element.attrib = {'id': self.id}

        for case in self.cases:
            element.append(get_casedb_element(case))

        return ElementTree.tostring(element, encoding="utf-8")

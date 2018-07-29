from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.case.mock import CaseBlock

# need all imports used by the doc tests here
from datetime import datetime                       # noqa: F401
from xml.etree import cElementTree as ElementTree   # noqa: F401

__test__ = {
    'caseblock': CaseBlock
}

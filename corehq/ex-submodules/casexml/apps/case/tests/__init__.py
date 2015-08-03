import logging
from casexml.apps.case.mock import CaseBlock, CaseBlockError

try:
    from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
    from .test_bugs import *
    from .test_db_accessors import *
    from .test_dbcache import *
    from .test_dynamic_properties import *
    from .test_exclusion import *
    from .test_extract_caseblocks import *
    from .test_factory import *
    from .test_force_save import *
    from .test_from_xform import *
    from .test_indexes import *
    from .test_multi_case_submits import *
    from .test_multimedia import *
    from .test_out_of_order_processing import *
    from .test_rebuild import *
    from .test_signals import *
    from .test_tags import *
    from .test_v2_parsing import *
    from .test_domains import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    logging.exception(str(e))
    raise

# need all imports used by the doc tests here
from datetime import datetime
from xml.etree import ElementTree

__test__ = {
    'caseblock': CaseBlock
}

from .test_filters import *
from .test_indicator_config import *
from .test_indicators import *
from .test_pillow import *
from .test_report_charts import *
from .test_report_config import *
from .test_report_filters import *
from .test_utils import *

from corehq.apps.userreports.getters import recursive_lookup

__test__ = {
    'recursive_lookup': recursive_lookup
}

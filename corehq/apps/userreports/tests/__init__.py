from .test_app_manager_integration import *
from .test_columns import *
from .test_custom_data_sources import *
from .test_custom_reports import *
from .test_export import *
from .test_expressions import *
from .test_filters import *
from .test_getters import *
from .test_data_source_config import *
from .test_data_source_repeats import *
from .test_multi_db import *
from .test_indicators import *
from .test_pillow import *
from .test_report_builder import *
from .test_report_charts import *
from .test_report_config import *
from .test_report_filters import *
from .test_transforms import *
from .test_utils import *
from .test_view import *
from .test_dbaccessors import *

from corehq.apps.userreports.expressions.getters import recursive_lookup

__test__ = {
    'recursive_lookup': recursive_lookup
}

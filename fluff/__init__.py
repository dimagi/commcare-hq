from fluff import exceptions
from fluff.exceptions import EmitterValidationError
from fluff.signals import BACKEND_SQL, BACKEND_COUCH
from .calculators import Calculator
from .const import *
from .emitters import custom_date_emitter, custom_null_emitter, date_emitter, null_emitter
from .filters import filter_by
from .indicators import AttributeGetter, FlatField, IndicatorDocument
from .pillow import FluffPillow
from .signals import indicator_document_updated
import fluff.util


default_app_config = 'fluff.app_config.FluffAppConfig'


try:
    # make sure this module gets called, as it is auto-registering
    import fluff.sync_couchdb
except ImportError:
    pass

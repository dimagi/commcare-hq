from corehq.apps.sms.forms import BackendForm
from corehq.apps.sms.mixin import SMSBackend
from dimagi.utils.couch.database import get_safe_write_kwargs
from dimagi.ext.couchdbkit import *

# TODO: What uses this? There already is a test backend

class TestBackend(SMSBackend):
    to_console = BooleanProperty(default=False)

    @classmethod
    def get_api_id(cls):
        return "TEST"

    def send(self, msg, *args, **kwargs):
        """
        The test backend does very little.
        """
        if self.to_console:
            print msg

    @classmethod
    def get_form_class(cls):
        return BackendForm

    @classmethod
    def get_generic_name(cls):
        return "Test Backend"

def bootstrap(id=None, to_console=True):
    """
    Create an instance of the test backend in the database
    """
    backend = TestBackend(
        description='test backend',
        is_global=True,
        to_console=to_console,
    )
    if id:
        backend._id = id
        backend.name = id.strip().upper()
    backend.save(**get_safe_write_kwargs())
    return backend


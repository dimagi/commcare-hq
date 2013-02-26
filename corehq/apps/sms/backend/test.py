from corehq.apps.sms.mixin import MobileBackend

def bootstrap(id=None, to_console=''):
    """
    Create an instance of the test backend in the database
    """
    backend = MobileBackend(
        domain=[],
        description='test backend',
        outbound_module='corehq.apps.sms.backend.test',
        outbound_params={'to_console': True}
    )
    if id:
        backend._id = id
    backend.save()
    return backend

def send(msg, *args, **kwargs):
    """
    The test backend does very little.
    """
    to_console = kwargs.get('to_console')
    if to_console:
        print msg

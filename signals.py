from django.dispatch import Signal


class ReceiverResult(object):
    """
    This class should be used to return from signals if
    you want to communicate something back to receiver.
    The most common (okay, only current) scenario for this
    is overriding the response to the user based on an 
    application's specific logic.
    """ 
    def __init__(self, response):
        self._response = response
    
    @property
    def response(self):
        """
        The response to return to the user.
        """ 
        return self._response
    
    def __str__(self):
        return self.response
    
post_received = Signal(providing_args=["posted"])

from django.dispatch import Signal


#Signal definitions

class Certainty(object):
    """
    How certain you are.  See the certainty property of the receiver 
    response.
    """
    NONE = 0
    MILD = 25
    AVERAGE = 50
    STRONG = 75
    CERTAIN = 100

class ReceiverResult(object):
    """
    This class should be used to return from signals if
    you want to communicate something back to receiver.
    The most common (okay, only current) scenario for this
    is overriding the response to the user based on an 
    application's specific logic.
    """ 
    def __init__(self, response, certainty):
        self._response = response
        self._certainty = certainty
    
    @property
    def response(self):
        """
        The response to return to the user.
        """ 
        return self._response
    
    @property
    def certainty(self):
        """
        The certainty of this response.  Higher is more certain.  When
        multiple responses are received the one with the highest certainty
        will win out.
        """ 
        return self._certainty
    
    def __cmp__(self, other):
        return self.certainty.__cmp__(other.certainty)
        
    def __str__(self):
        return self.response
    
form_received = Signal(providing_args=["posted"])
successful_form_received = Signal(providing_args=["posted"])




class BuildError(Exception):
    """Generic error for the Build Manager to throw.  Also
       supports wrapping a collection of other errors."""
    
    def __init__(self, msg, errors=[]):
        super(BuildError, self).__init__(msg)
        # reimplementing base message, since .message is deprecated in 2.6
        self.msg = msg 
        self.errors = errors
        
    def get_error_string(self, delim="\n"):
        '''Get the error string associated with any passed in errors, 
           joined by an optionally passed in delimiter''' 
        return delim.join([unicode(error) for error in self.errors])
    
    def __unicode__(self):
        return "%s\n%s" % (self.msg, self.get_error_string()) 

    def __str__(self):
        return unicode(self).encode('utf-8')
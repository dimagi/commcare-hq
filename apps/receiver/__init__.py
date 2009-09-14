from receiver.submitresponse import SubmitResponse
from django.http import HttpResponse

def duplicate_attachment(way_handled):
    '''Return a custom http response associated the handling
       of the xform.  In this case, telling the sender that
       they submitted a duplicate
       '''
    try:
        # NOTE: this possibly shouldn't be a "200" code, but it is for 
        # now because it's not clear how JavaRosa will handle 202.
        # see: http://code.dimagi.com/JavaRosa/wiki/ServerResponseFormat
        response = SubmitResponse(status_code=200, or_status_code=2020, 
                                  or_status="Duplicate Submission.",
                                  submit_id=way_handled.submission.id)
        return response.to_response()
    except Exception, e:
        logging.error("Problem in properly responding to instance data handling of %s" %
                      way_handled)

    
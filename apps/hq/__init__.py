import logging
from receiver.submitresponse import SubmitResponse

SUCCESSFUL_REGISTRATION = "Successful registration"

def registration_response(way_handled, additional_params):
    '''Return a custom http response associated the handling
       of the xform, in this case as a valid backup file.
    '''
    try:
        # Registrations will eventually respond with some smart information
        # about the outcome of the registration and the data that was created,
        # but for now this doesn't do anything special except override the 
        # status message to say that we understood what you were trying to do.
        response = SubmitResponse(status_code=200, 
                                  submit_id=way_handled.submission.id, 
                                  or_status_code=2000, 
                                  or_status=SUCCESSFUL_REGISTRATION)
        return response.to_response()
    except Exception, e:
        logging.error("Problem in properly responding to backup handling of %s: %s" % \
                      (way_handled, e.message))

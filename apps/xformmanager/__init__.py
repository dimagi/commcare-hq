import logging
from datetime import datetime, timedelta

from django.http import HttpResponse

from receiver.submitresponse import SubmitResponse

SUCCESSFUL_SUBMISSION = "Thanks!"

def instance_data(way_handled, additional_params):
    '''Return a custom http response associated the handling
       of the xform, in this case as a valid submission matched
       to a schema.
    '''
    try:
        if way_handled.submission.xform and \
           way_handled.submission.xform.has_linked_schema():
            meta = way_handled.submission.xform.get_linked_metadata()
            startdate = datetime.now().date() 
            enddate = startdate + timedelta(days=1)
            submits_today = meta.get_submission_count(startdate, enddate)
            startdate = datetime.min
            submits_all_time = meta.get_submission_count(startdate, enddate)
            response = SubmitResponse(status_code=200, forms_sent_today=submits_today,
                                      submit_id=way_handled.submission.id, 
                                      or_status_code=2000, 
                                      or_status=SUCCESSFUL_SUBMISSION,
                                      total_forms_sent=submits_all_time, 
                                      **additional_params)
                                      
            return response.to_response()
    except Exception, e:
        logging.error("Problem in properly responding to instance data handling of %s" %
                      way_handled)

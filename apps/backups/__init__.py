import logging
from datetime import datetime, timedelta

from django.http import HttpResponse

from receiver.submitresponse import SubmitResponse

SUCCESSFUL_BACKUP = "Successful backup"

def backup_response(way_handled, additional_params):
    '''Return a custom http response associated the handling
       of the xform, in this case as a valid backup file.
    '''
    try:
        from backups.models import Backup
        # Backups should only ever be posting as a single file
        # We don't know what it means if they're not
        if way_handled.submission.attachments.count() == 1:
            attachment = way_handled.submission.attachments.all()[0]
            backup = Backup.objects.get(attachment=attachment)
            response = SubmitResponse(status_code=200, 
                                      submit_id=way_handled.submission.id, 
                                      or_status_code=2000, 
                                      or_status=SUCCESSFUL_BACKUP,
                                      **{"BackupId": backup.id })
            return response.to_response()
    except Exception, e:
        logging.error("Problem in properly responding to backup handling of %s: %s" % \
                      (way_handled, e.message))

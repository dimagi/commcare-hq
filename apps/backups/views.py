from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from backups.models import Backup

def restore(request, backup_id):
    """Get a backup file by id"""
    backup = get_object_or_404(Backup,id=backup_id)
    response = HttpResponse(mimetype='text/xml')
    response.write(backup.attachment.get_contents()) 
    return response
                               
    
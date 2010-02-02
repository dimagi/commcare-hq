# Create your webui views here.


# czue: moved from receiver app.  This is likely mostly useles  
def restore(request, code_id, template_name="receiver/restore.html"):
    context = {}            
    logging.debug("begin restore()")
    # need to somehow validate password, presmuably via the header objects.
    restore = Backup.objects.all().filter(backup_code=code_id)
    if len(restore) != 1:
        template_name="receiver/nobackup.html"
        return render_to_response(request, template_name, context,mimetype='text/plain')
    original_submission = restore[0].submission
    attaches = Attachment.objects.all().filter(submission=original_submission)
    for attach in attaches:
        if attach.attachment_content_type == "text/xml":
            response = HttpResponse(mimetype='text/xml')
            fin = open(attach.filepath,'r')
            txt = fin.read()
            fin.close()
            response.write(txt)
            
            verify_checksum = hashlib.md5(txt).hexdigest()
            if verify_checksum == attach.checksum:                
                return response
            else:               
                continue
    
    template_name="receiver/nobackup.html"
    return render_to_response(request, template_name, context,mimetype='text/plain')
        

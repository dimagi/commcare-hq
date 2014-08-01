def set_file_download(response, filename):
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename

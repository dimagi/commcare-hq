Using the shared NFS drive
==========================

On our production servers (and staging) we have an NFS drive set up that we can use for a number of things:

* store files that are generated asynchronously for retrieval in a later request
  * previously we needed to save these files to Redis so that they would be available to all the Django workers
  on the next request
  * doing this has the added benefit of allowing apache / nginx to handle the file transfer instead of Django
* store files uploaded by the user that require asynchronous processing

Using apache / nginx to handle downloads
----------------------------------------

::

    import os
    import tempfile
    from wsgiref.util import FileWrapper
    from django.conf import settings
    from django.http import StreamingHttpResponse
    from django_transfer import TransferHttpResponse

    transfer_enabled = settings.SHARED_DRIVE_CONF.transfer_enabled
    if transfer_enabled:
        path = os.path.join(settings.SHARED_DRIVE_CONF.transfer_dir, uuid.uuid4().hex)
    else:
        fd, path = tempfile.mkstemp()
        os.close(fd)

    make_file(path)

    if transfer_enabled:
        response = TransferHttpResponse(path, content_type=self.zip_mimetype)
    else:
        response = StreamingHttpResponse(FileWrapper(open(path)), content_type=self.zip_mimetype)

    response['Content-Length'] = os.path.getsize(fpath)
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename
    return response

This also works for files that are generated asynchronously::

    @task
    def generate_download(download_id):
        use_transfer = settings.SHARED_DRIVE_CONF.transfer_enabled
        if use_transfer:
            path = os.path.join(settings.SHARED_DRIVE_CONF.transfer_dir, uuid.uuid4().hex)
        else:
            fd, path = tempfile.mkstemp()
            os.close(fd)

        generate_file(path)

        common_kwargs = dict(
            mimetype='application/zip',
            content_disposition='attachment; filename="{fname}"'.format(fname=filename),
            download_id=download_id,
        )
        if use_transfer:
            expose_file_download(
                path,
                use_transfer=use_transfer,
                **common_kwargs
            )
        else:
            expose_cached_download(
                FileWrapper(open(path)),
                expiry=(1 * 60 * 60),
                **common_kwargs
            )

Saving uploads to the NFS drive
-------------------------------
For files that are uploaded and require asynchronous processing e.g. imports, you can also use the NFS drive::

    from soil.util import expose_file_download, expose_cached_download

    uploaded_file = request.FILES.get('Filedata')
    if hasattr(uploaded_file, 'temporary_file_path') and settings.SHARED_DRIVE_CONF.temp_dir:
        path = settings.SHARED_DRIVE_CONF.get_temp_file()
        shutil.move(uploaded_file.temporary_file_path(), path)
        saved_file = expose_file_download(path, expiry=60 * 60)
    else:
        uploaded_file.file.seek(0)
        saved_file = expose_cached_download(uploaded_file.file.read(), expiry=(60 * 60))

    process_uploaded_file.delay(saved_file.download_id)

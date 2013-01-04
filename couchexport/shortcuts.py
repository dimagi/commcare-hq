import logging
from zipfile import ZipFile
from django.core.servers.basehttp import FileWrapper
from couchexport.models import FakeSavedExportSchema
from django.http import HttpResponse
from StringIO import StringIO
from unidecode import unidecode
from couchexport.util import get_schema_index_view_keys

def get_export_files(export_tag, format=None, previous_export_id=None, filter=None,
                     use_cache=True, max_column_size=2000, separator='|'):
    """This function only exists for backwards compatibility"""

    return FakeSavedExportSchema(index=export_tag).get_export_files(
        format=format,
        previous_export_id=previous_export_id,
        filter=filter,
        use_cache=use_cache,
        max_column_size=max_column_size,
        separator=separator
    )

def export_data_shared(export_tag, format=None, filename=None,
                       previous_export_id=None, filter=None,
                       use_cache=True, max_column_size=2000,
                       separator='|'):
    """
    Shared method for export. If there is data, return an HTTPResponse
    with the appropriate data. If there is not data returns None.
    """
    if not filename:
        filename = export_tag
    
    tmp, checkpoint = FakeSavedExportSchema(index=export_tag).get_export_files(
        format=format,
        previous_export_id=previous_export_id,
        filter=filter,
        use_cache=use_cache,
        max_column_size=max_column_size,
        separator=separator
    )
    
    if checkpoint:
        return export_response(tmp, format, filename, checkpoint)
    else: 
        return None
    
def export_response(file, format, filename, checkpoint=None):
    """
    Get an http response for an export
    file can be either a StringIO
    or an open file object (which this function is responsible for closing)

    """
    from couchexport.export import Format
    if not filename:
        filename = "NAMELESS EXPORT"
        
    format = Format.from_format(format)
    if isinstance(file, StringIO):
        payload = file.getvalue()
        # I don't know why we need to close the file. Keeping around.
        file.close()
    else:
        payload = FileWrapper(file)

    response = HttpResponse(payload, mimetype=format.mimetype)

    if format.download:
        try:
            filename = unidecode(filename)
        except Exception:
            logging.exception("Error with filename: %r" % filename)
            filename = "data"
        finally:
            response['Content-Disposition'] = 'attachment; filename="{filename}.{format.extension}"'.format(
                filename=filename,
                format=format
            )

    if checkpoint:
        response['X-CommCareHQ-Export-Token'] = checkpoint.get_id

    return response

def export_raw_data(export_tag, filename=None):
    # really this shouldn't be here, but keeping it for now                   
    from couchforms.models import XFormInstance
    xform_instances = XFormInstance.view('couchexport/schema_index',
                                         include_docs=True,
                                         reduce=False,
                                         **get_schema_index_view_keys(export_tag))
    f = StringIO()
    zipfile = ZipFile(f, 'w')
    for xform_instance in xform_instances:
        form_xml = xform_instance.fetch_attachment('form.xml').encode('utf-8')
        zipfile.writestr("%s.xml" % xform_instance.get_id, form_xml)
    zipfile.close()
    f.flush()
    response = HttpResponse(f.getvalue())
    f.close()
    response['Content-Type'] = "application/zip"
    response['Content-Disposition'] = "attachment; filename=%s.zip" % filename
    return response

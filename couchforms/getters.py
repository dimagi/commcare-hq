from django.utils.datastructures import MultiValueDictKeyError
from couchforms.const import MAGIC_PROPERTY, MULTIPART_FILENAME_ERROR

__all__ = ['get_path', 'get_instance_and_attachment']


def get_path(request):
    return request.path


def get_instance_and_attachment(request):
    try:
        return request._instance_and_attachment
    except AttributeError:
        pass
    attachments = {}
    if request.META['CONTENT_TYPE'].startswith('multipart/form-data'):
        # it's an standard form submission (eg ODK)
        # this does an assumption that ODK submissions submit using the form parameter xml_submission_file
        # todo: this should be made more flexibly to handle differeing params for xform submission
        try:
            instance = request.FILES[MAGIC_PROPERTY].read()
        except MultiValueDictKeyError:
            instance = MULTIPART_FILENAME_ERROR
        else:
            for key, item in request.FILES.items():
                if key != MAGIC_PROPERTY:
                    attachments[key] = item
    else:
        #else, this is a raw post via a j2me client of xml (or touchforms)
        #todo, multipart raw submissions need further parsing capacity.
        instance = request.raw_post_data
    request._instance_and_attachment = (instance, attachments)
    return instance, attachments

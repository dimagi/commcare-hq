from django.utils.datastructures import MultiValueDictKeyError
from couchforms.const import MAGIC_PROPERTY, VALID_ATTACHMENT_FILE_EXTENSIONS
import logging
from datetime import datetime
from django.conf import settings

from couchforms.exceptions import (
    EmptyPayload,
    MultipartEmptyPayload,
    MultipartFilenameError,
    PayloadTooLarge,
    InvalidAttachmentFileError,
    InvalidSubmissionFileExtensionError,
    AttachmentSizeTooLarge,
)
from dimagi.utils.parsing import string_to_utc_datetime
from dimagi.utils.web import get_ip, get_site_domain, IP_RE


__all__ = ['get_path', 'get_instance_and_attachment',
           'get_location', 'get_received_on', 'get_date_header',
           'get_submit_ip', 'get_last_sync_token', 'get_openrosa_headers']

# Header that formplayer adds to request to store user ip address on form submission
COMMCAREHQ_ORIGIN_IP = 'HTTP_X_COMMCAREHQ_ORIGIN_IP'

def get_path(request):
    return request.path


class MultimediaBug(Exception):
    pass


def get_instance_and_attachment(request):
    try:
        return request._instance_and_attachment
    except AttributeError:
        pass
    attachments = {}
    if request.META['CONTENT_TYPE'].startswith('multipart/form-data'):
        # ODK submission; of the form
        # $ curl --form 'xml_submission_file=@form.xml' $URL
        if list(request.POST):
            raise MultimediaBug("Received a submission with POST.keys()")

        try:
            instance_file = request.FILES[MAGIC_PROPERTY]
        except MultiValueDictKeyError:
            raise MultipartFilenameError()
        else:
            if instance_file.size > settings.MAX_UPLOAD_SIZE:
                logging.info("Domain {request.domain} attempted to submit a form exceeding the allowed size")
                raise PayloadTooLarge()
            if not _valid_instance_file_extension(instance_file):
                raise InvalidSubmissionFileExtensionError()
            instance = instance_file.read()
            for key, item in request.FILES.items():
                if key != MAGIC_PROPERTY:
                    if _attachment_exceeds_size_limit(item):
                        raise AttachmentSizeTooLarge()
                    if not _valid_attachment_file(item):
                        raise InvalidAttachmentFileError()
                    attachments[key] = item
        if not instance:
            raise MultipartEmptyPayload()
    else:
        # touchforms; of the form
        # $ curl --data '@form.xml' $URL
        instance = request.body
        if not instance:
            raise EmptyPayload()
    request._instance_and_attachment = (instance, attachments)
    return instance, attachments


def _valid_instance_file_extension(file):
    return _valid_file_extension(file.name, ['xml'])


def _valid_file_extension(filename, valid_extensions):
    if "." not in filename:
        return False
    file_extension = filename.rsplit(".", 1)[-1]
    return file_extension in valid_extensions


def _valid_attachment_file(file):
    return _valid_attachment_file_extension(file) or _valid_attachment_file_mimetype(file)


def _valid_attachment_file_extension(file):
    return _valid_file_extension(file.name, VALID_ATTACHMENT_FILE_EXTENSIONS)


def _valid_attachment_file_mimetype(file):
    return (
        file.content_type.startswith(("audio/", "image/", "video/"))
        # default mimetype set by CommCare
        or file.content_type == "application/octet-stream"
        # supported by formplayer
        or file.content_type == "application/pdf"
    )


def _attachment_exceeds_size_limit(file):
    return file.size > settings.MAX_UPLOAD_SIZE_ATTACHMENT


def get_location(request=None):
    # this is necessary, because www.commcarehq.org always uses https,
    # but is behind a proxy that won't necessarily look like https
    if hasattr(settings, "OVERRIDE_LOCATION"):
        return settings.OVERRIDE_LOCATION
    if request is None:
        prefix = settings.DEFAULT_PROTOCOL
    else:
        prefix = "https" if request.is_secure() else "http"
    return "%s://%s" % (prefix, get_site_domain())


def get_received_on(request):
    received_on = request.META.get('HTTP_X_SUBMIT_TIME')
    if received_on:
        return string_to_utc_datetime(received_on)
    else:
        return None


def get_date_header(request):
    date_header = request.META.get('HTTP_DATE')
    if date_header:
        # comes in as:
        # Mon, 11 Apr 2011 18:24:43 GMT
        # goes out as:
        # 2011-04-11T18:24:43Z
        try:
            date = datetime.strptime(date_header, "%a, %d %b %Y %H:%M:%S GMT")
            date = datetime.strftime(date, "%Y-%m-%dT%H:%M:%SZ")
        except:
            logging.error((
                "Receiver app: incoming submission has a date header "
                "that we can't parse: '%s'"
            ) % date_header)
            date = date_header
        date_header = date
    else:
        date_header = None
    return date_header


def get_submit_ip(request):
    from corehq.apps.ota.decorators import ORIGIN_TOKEN_HEADER, validate_origin_token
    x_commcarehq_origin_ip = request.META.get(COMMCAREHQ_ORIGIN_IP, None)
    origin_token = request.META.get(ORIGIN_TOKEN_HEADER, None)
    if x_commcarehq_origin_ip:
        is_ip_address = IP_RE.match(x_commcarehq_origin_ip)
        if is_ip_address and validate_origin_token(origin_token):
            return x_commcarehq_origin_ip
    return get_ip(request)


def get_last_sync_token(request):
    return getattr(request, 'last_sync_token', None)


def get_openrosa_headers(request):
    return getattr(request, 'openrosa_headers', None)

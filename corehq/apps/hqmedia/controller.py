from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

class BaseMultimediaUploadController(object):
    is_multi_file = False
    uploader_class = None
    media_type = None

    errors_template_name = "hqmedia/uploader/errors.html"

    def __init__(self, name, destination):
        self.name = name
        self.destination = destination

    def __getattribute__(self, item):
        if item.endswith("_template"):
            template_name = getattr(self, "%s_name" % item)
            if template_name:
                return render_to_string(template_name, {})
            return None
        return super(BaseMultimediaUploadController, self).__getattribute__(item)

    @property
    def licensing_params(self):
        return ['shared', 'license', 'author', 'attribution-notes']

    @property
    def upload_params(self):
        """
            Extra parameters that get sent to the processor once the file is uploaded.
        """
        return {}

    @property
    def supported_files(self):
        """
            A list of dicts of supported file extensions by the YUI Uploader widget.
        """
        raise NotImplementedError("You must specify a list of supported files for this uploader.")

    @property
    def processing_url(self):
        from corehq.apps.hqmedia.views import MultimediaUploadStatusView
        return reverse(MultimediaUploadStatusView.name)


class MultimediaBulkUploadController(BaseMultimediaUploadController):
    is_multi_file = True
    uploader_class = "HQMediaBulkUploadController"
    media_type = "bulk"

    queue_template_name = "hqmedia/uploader/queue_multi.html"
    status_template_name = "hqmedia/uploader/status_multi.html"
    details_template_name = "hqmedia/uploader/details_multi.html"

    @property
    def upload_params(self):
        return {
            'replace_existing': False,
        }

    @property
    def supported_files(self):
        return [
            {
                'description': 'Zip',
                'extensions': '*.zip',
            },
        ]


class BaseMultimediaFileUploadController(BaseMultimediaUploadController):
    uploader_class = "HQMediaFileUploadController"
    queue_template_name = "hqmedia/uploader/queue_single.html"


class MultimediaImageUploadController(BaseMultimediaFileUploadController):
    media_type = ugettext_noop("image")
    existing_file_template_name = "hqmedia/uploader/preview_image_single.html"

    @property
    def supported_files(self):
        return [
            {
                'description': 'Images',
                'extensions': '*.jpg;*.png;*.gif',
            },
        ]


class MultimediaAudioUploadController(BaseMultimediaFileUploadController):
    media_type = ugettext_noop("audio")

    existing_file_template_name = "hqmedia/uploader/preview_audio_single.html"

    @property
    def supported_files(self):
        return [
            {
                'description': 'Audio',
                'extensions': '*.mp3;*.wav',
            },
        ]

from django.template.loader import render_to_string
from django.utils.translation import gettext_noop


class BaseMultimediaFileUploadController(object):
    """
        Media type is the user-facing term for the type of media that the uploader is uploading
    """
    media_type = None
    uploader_type = "file"

    def __init__(self, slug, destination):
        self.slug = slug
        self.destination = destination

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
    def js_options(self):
        options = {
            'uploadURL': self.destination,
            'uploadParams': self.upload_params,
            'errorsTemplate': render_to_string("hqmedia/uploader/errors.html"),
            'queueTemplate': render_to_string("hqmedia/uploader/queue_single.html"),
        }
        if hasattr(self, 'existing_file_template'):
            options.update({'existingFileTemplate': render_to_string(self.existing_file_template)})

        return {
            'slug': self.slug,
            'uploader_type': self.uploader_type,
            'options': options,
        }


class MultimediaImageUploadController(BaseMultimediaFileUploadController):
    media_type = gettext_noop("image")
    existing_file_template = "hqmedia/uploader/preview_image_single.html"


class MultimediaLogoUploadController(MultimediaImageUploadController):
    media_type = gettext_noop("logo")


class MultimediaAudioUploadController(BaseMultimediaFileUploadController):
    media_type = gettext_noop("audio")

    existing_file_template = "hqmedia/uploader/preview_audio_single.html"


class MultimediaVideoUploadController(BaseMultimediaFileUploadController):
    media_type = gettext_noop("video")

    existing_file_template = "hqmedia/uploader/preview_video_single.html"


class MultimediaHTMLUploadController(BaseMultimediaFileUploadController):
    media_type = gettext_noop("text")

    existing_file_template = "hqmedia/uploader/preview_html_single.html"

    @property
    def upload_params(self):
        return {
            'path': 'jr://file/commcare/text/%s.html' % self.slug,
            'replace_attachment': True,
        }

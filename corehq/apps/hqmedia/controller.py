from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_noop


class BaseMultimediaFileUploadController(object):
    """
        Media type is the user-facing term for the type of media that the uploader is uploading
    """
    media_type = None
    uploader_type = "file"

    errors_template = "hqmedia/uploader/errors.html"
    queue_template = "hqmedia/uploader/queue_single.html"

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
    def supported_files(self):
        """
            A list of dicts of supported file extensions by the YUI Uploader widget.
        """
        raise NotImplementedError("You must specify a list of supported files for this uploader.")

    @property
    def processing_url(self):
        from corehq.apps.hqmedia.views import MultimediaUploadStatusView
        return reverse(MultimediaUploadStatusView.urlname)

    @property
    def js_options(self):
        options = {
            'allowCloseDuringUpload': True,
            'fileFilters': self.supported_files,
            'uploadURL': self.destination,
            'processingURL': self.processing_url,
            'uploadParams': self.upload_params,
            'licensingParams': self.licensing_params,
        }
        if hasattr(self, 'queue_template'):
            options.update({'queueTemplate': render_to_string(self.queue_template)})
        if hasattr(self, 'status_template'):
            options.update({'statusTemplate': render_to_string(self.status_template)})
        if hasattr(self, 'details_template'):
            options.update({'detailsTemplate': render_to_string(self.details_template)})
        if hasattr(self, 'errors_template'):
            options.update({'errorsTemplate': render_to_string(self.errors_template)})
        if hasattr(self, 'existing_file_template'):
            options.update({'existingFileTemplate': render_to_string(self.existing_file_template)})

        return {
            'slug': self.slug,
            'uploader_type': self.uploader_type,
            'media_type': self.media_type,
            'options': options,
        }


class MultimediaImageUploadController(BaseMultimediaFileUploadController):
    media_type = gettext_noop("image")
    existing_file_template = "hqmedia/uploader/preview_image_single.html"

    @property
    def supported_files(self):
        return [
            {
                'description': 'Images',
                'extensions': '*.jpg;*.png;*.gif',
            },
        ]


class MultimediaLogoUploadController(MultimediaImageUploadController):
    media_type = gettext_noop("logo")


class MultimediaAudioUploadController(BaseMultimediaFileUploadController):
    media_type = gettext_noop("audio")

    existing_file_template = "hqmedia/uploader/preview_audio_single.html"

    @property
    def supported_files(self):
        return [
            {
                'description': 'Audio',
                'extensions': '*.mp3;*.wav',
            },
        ]


class MultimediaVideoUploadController(BaseMultimediaFileUploadController):
    media_type = gettext_noop("video")

    existing_file_template = "hqmedia/uploader/preview_video_single.html"

    @property
    def supported_files(self):
        return [
            {
                'description': 'Video',
                'extensions': '*.3gp',
            },
        ]


class MultimediaHTMLUploadController(BaseMultimediaFileUploadController):
    media_type = gettext_noop("text")

    existing_file_template = "hqmedia/uploader/preview_html_single.html"

    @property
    def upload_params(self):
        return {
            'path': 'jr://file/commcare/text/%s.html' % self.slug,
            'replace_attachment': True,
        }

    @property
    def supported_files(self):
        return [
            {
                'description': 'HTML',
                'extensions': '*.htm;*.html',
            },
        ]

from django.core.urlresolvers import reverse


class BaseMultimediaUploadController(object):
    is_multi_file = False

    queue_template_name = None
    status_template_name = None
    details_template_name = None
    errors_template_name = None

    def __init__(self, name, destination,
                 container_id=None, marker_id=None, modal_id=None):
        """

        """
        self.name = name
        self.destination = destination

        self.container_id = container_id
        self.marker_id = marker_id
        self.modal_id = modal_id


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
    def allowed_files(self):
        """
            A list of dicts of accepted file extensions by the YUI Uploader widget.
        """
        raise NotImplementedError("You must specify a list of allowed files for this uploader.")

    @property
    def processing_url(self):
        from corehq.apps.hqmedia.views import MultimediaUploadStatusView
        return reverse(MultimediaUploadStatusView.name)





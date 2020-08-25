import lxml.etree
from memoized import memoized
import xml2json

from corehq.form_processor.extension_points import get_form_submission_context_class
from corehq.form_processor.utils.metadata import scrub_meta

from couchforms.util import legacy_notification_assert


class SubmissionFormContext(object):
    def __init__(self, submission_post):
        self.submission_post = submission_post
        self._instance = submission_post.instance

    def get_instance_xml(self):
        try:
            return xml2json.get_xml_from_string(self._instance)
        except xml2json.XMLSyntaxError:
            return None

    def get_instance(self):
        return self._instance

    def update_instance(self, xml):
        self._instance = lxml.etree.tostring(xml)

    def pre_process_form(self):
        # over write this method to add pre processing to form
        pass

    def post_process_form(self, xform):
        self.submission_post.set_submission_properties(xform)
        found_old = scrub_meta(xform)
        legacy_notification_assert(not found_old, 'Form with old metadata submitted', xform.form_id)
        self.submission_post.invalidate_caches(xform)


@memoized
def form_submission_context_class():
    return get_form_submission_context_class() or SubmissionFormContext

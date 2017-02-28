from .interface import PillowProcessor
from .utils import mark_has_submission, mark_latest_submission


class FormSubmissionMetadataTrackerProcessor(PillowProcessor):
    """
    Processor used to process each form and mark the corresponding application as
    having submissions (has_submissions = True).
    """

    def process_change(self, pillow_instance, change):
        if change.deleted or change.metadata is None:
            return

        doc = change.get_document()
        if not doc:
            return

        build_id = doc.get('build_id')
        domain = change.metadata.domain

        if build_id and domain:
            # Marks if a build has a submission. The function is cached based on domain
            # and build_id so that there is no need to fetch the app again after this
            # is called. Any subsequent calls with the same arguments will result in
            # the same effect, an app having has_submissions set to True.
            mark_has_submission(domain, build_id)

        user_id = doc.get('user_id')
        received_on = doc.get('received_on')

        if user_id and domain and received_on:
            mark_latest_submission(domain, user_id, received_on)

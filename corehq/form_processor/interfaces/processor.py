from corehq.form_processor.utils import to_generic
from corehq.util.test_utils import unit_testing_only
from couchforms.util import process_xform
from casexml.apps.case.util import post_case_blocks


class FormProcessorInterface(object):
    """
    The FormProcessorInterface serves as the base transactions that take place in forms. Different
    backends can implement this class in order to make common interface.
    """

    @staticmethod
    @to_generic
    @unit_testing_only
    def post_xform(instance_xml, attachments=None, process=None, domain='test-domain'):
        """
        create a new xform and releases the lock

        this is a testing entry point only and is not to be used in real code

        """
        if not process:
            def process(xform):
                xform.domain = domain
        xform_lock = process_xform(instance_xml, attachments=attachments, process=process, domain=domain)
        with xform_lock as xforms:
            for xform in xforms:
                xform.save()
            return xforms[0]

    @staticmethod
    def submit_form_locally(instance, domain='test-domain', **kwargs):
        from corehq.apps.receiverwrapper.util import submit_form_locally
        response, xform, cases = submit_form_locally(instance, domain, **kwargs)
        # response is an iterable so @to_generic doesn't work
        return response, xform.to_generic(), [case.to_generic() for case in cases]

    @staticmethod
    @to_generic
    def post_case_blocks(case_blocks, form_extras=None, domain=None):
        return post_case_blocks(case_blocks, form_extras=form_extras, domain=domain)

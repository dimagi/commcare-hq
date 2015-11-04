class AbstractXFormInstance(object):

    def form_id(self):
        raise NotImplementedError()

    def auth_context(self):
        raise NotImplementedError()

    def form_data(self):
        raise NotImplementedError()

    def get_data(self, xpath):
        raise NotImplementedError()

    def get_attachment(self, attachment_name):
        raise NotImplementedError()

    def archive(self, xform_generic, user=None):
        raise NotImplementedError()

    def unarchive(self, xform_generic, user=None):
        raise NotImplementedError()

    def get_xml_element(self):
        raise NotImplementedError()

    @classmethod
    def get(self, xform_id):
        raise NotImplementedError()

    def save(self, *args, **kwargs):
        raise NotImplementedError()

    def set_submission_properties(self, submission_post):
        raise NotImplementedError()

    def to_json(self):
        raise NotImplementedError()


class AbstractCommCareCase(object):

    def id(self):
        raise NotImplementedError()

    def hard_delete(self):
        raise NotImplementedError()

    def soft_delete(self):
        raise NotImplementedError()

    def get_attachment(self, attachment_name):
        raise NotImplementedError()

    def is_deleted(self):
        raise NotImplementedError()

    @classmethod
    def get_cases(cls, ids):
        raise NotImplementedError()

    @classmethod
    def get_case_xform_ids(cls, case_id):
        raise NotImplementedError()

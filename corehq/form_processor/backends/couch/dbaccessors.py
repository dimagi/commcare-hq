from couchforms.dbaccessors import get_forms_by_type


class FormAccessorCouch(object):

    @staticmethod
    def get_forms_by_type(domain, type_, recent_first=False, limit=None):
        return get_forms_by_type(domain, type_, recent_first, limit)

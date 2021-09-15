from corehq.form_processor.interfaces.dbaccessors import (
    AbstractCaseAccessor, AbstractFormAccessor)


class FormAccessorCouch(AbstractFormAccessor):

    @staticmethod
    def form_exists(form_id, domain=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_form(form_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_forms(form_ids, ordered=False):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_form_ids_in_domain_by_type(domain, type_):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_forms_by_type(domain, type_, limit, recent_first=False):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_with_attachments(form_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_attachment_content(form_id, attachment_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def save_new_form(form):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def update_form_problem_and_state(form):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_deleted_form_ids_for_user(domain, user_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_form_ids_for_user(domain, user_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def set_archived_state(form, archive, user_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def soft_delete_forms(domain, form_ids, deletion_date=None, deletion_id=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def soft_undelete_forms(domain, form_ids):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def modify_attachment_xml_and_metadata(form_data, form_attachment_new_xml, new_username):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def iter_form_ids_by_xmlns(domain, xmlns=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")


class CaseAccessorCouch(AbstractCaseAccessor):

    @staticmethod
    def case_exists(case_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_case_ids_that_exist(domain, case_ids):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_case_xform_ids(case_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_case_ids_in_domain(domain, type=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_case_ids_in_domain_by_owners(domain, owner_ids, closed=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_open_case_ids_for_owner(domain, owner_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_closed_case_ids_for_owner(domain, owner_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_open_case_ids_in_domain_by_type(domain, case_type, owner_ids=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_case_ids_modified_with_owner_since(domain, owner_id, reference_date):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_extension_case_ids(domain, case_ids, include_closed=True, exclude_for_case_type=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_indexed_case_ids(domain, case_ids):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_reverse_indexed_cases(domain, case_ids, case_types=None, is_closed=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_last_modified_dates(domain, case_ids):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_all_reverse_indices_info(domain, case_ids):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_attachment_content(case_id, attachment_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_case_by_domain_hq_user_id(domain, user_id, case_type):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_cases_by_external_id(domain, external_id, case_type=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def soft_delete_cases(domain, case_ids, deletion_date=None, deletion_id=None):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def soft_undelete_cases(domain, case_ids):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_deleted_case_ids_by_owner(domain, owner_id):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

    @staticmethod
    def get_case_owner_ids(domain):
        raise NotImplementedError("should not be used since forms & cases were migrated to SQL")

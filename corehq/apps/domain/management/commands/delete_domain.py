from corehq.apps.domain.delete_domain_base import DomainBaseCommand


class Command(DomainBaseCommand):
    help = "Deletes the given domain and its contents"

    def confirmation_message(self, domain_name):
        return f"""
                Are you sure you want to delete the domain "{domain_name}" and all of it's data?
                This operation is not reversible and all forms and cases will be PERMANENTLY deleted.

                Type the domain's name again to continue, or anything else to cancel:
                """

    def action_message(self, domain_name):
        return f'Soft-Deleting domain "{domain_name}" ' \
               '(i.e. switching its type to Domain-Deleted, ' \
               'which will prevent anyone from reusing that domain)'

    def handle_domain(self, domain_obj):
        domain_obj.delete(leave_tombstone=True)

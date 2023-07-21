from corehq.apps.domain.deletion import apply_sms_deletion_operations
from corehq.apps.domain.delete_domain_base import DomainBaseCommand


class Command(DomainBaseCommand):
    help = "Deletes sms and email logs for a given domain"

    def confirmation_message(self, domain_name):
        return f"""
                Are you sure you want to delete all sms and email logs from domain "{domain_name}"?
                This operation is not reversible.

                Type the domain's name again to continue, or anything else to cancel:
                """

    def action_message(self, domain_name):
        return f'Deleting sms and email logs from domain "{domain_name}"'

    def handle_domain(self, domain_obj):
        apply_sms_deletion_operations(domain_obj.name)

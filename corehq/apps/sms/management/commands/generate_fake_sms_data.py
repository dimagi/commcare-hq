from django.core.management import BaseCommand

from corehq.apps.sms.tests.data_generator import create_fake_sms


class Command(BaseCommand):
    help = """
        Generates a few fake SMS message models for a domain, for testing.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('num_messages', type=int, help="The number of SMS messages to create")

    def handle(self, domain, num_messages, **kwargs):
        for i in range(num_messages):
            create_fake_sms(domain, randomize=True)
        print(f'successfully created {num_messages} messages in {domain}')

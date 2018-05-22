from __future__ import absolute_import
from __future__ import unicode_literals
from couchexport.export import export_raw
from custom.fri.models import FRIMessageBankMessage, FRIRandomizedMessage, FRIExtraMessage
from django.core.management.base import BaseCommand
from io import open


class Command(BaseCommand):

    def write_result_to_file(self, model_name, result, fields):
        with open('%s.xlsx' % model_name, 'wb') as f:
            headers = fields
            excel_data = []

            for obj in result:
                excel_data.append((getattr(obj, field) for field in fields))

            export_raw(
                ((model_name, headers), ),
                ((model_name, excel_data), ),
                f
            )

    def handle(self, **options):
        self.write_result_to_file(
            'FRIMessageBankMessage',
            FRIMessageBankMessage.view('fri/message_bank', include_docs=True).all(),
            ('_id', 'domain', 'risk_profile', 'message', 'fri_id')
        )

        self.write_result_to_file(
            'FRIRandomizedMessage',
            FRIRandomizedMessage.view('fri/randomized_message', include_docs=True).all(),
            ('_id', 'domain', 'case_id', 'message_bank_message_id', 'order')
        )

        self.write_result_to_file(
            'FRIExtraMessage',
            FRIExtraMessage.view('fri/extra_message', include_docs=True).all(),
            ('_id', 'domain', 'message_id', 'message')
        )

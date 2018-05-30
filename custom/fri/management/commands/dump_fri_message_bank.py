from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from custom.fri.models import FRIMessageBankMessage, FRIRandomizedMessage, FRIExtraMessage
from django.core.management.base import BaseCommand
from six import moves


class Command(BaseCommand):

    def delete_docs(self, model_name, result):
        print("\nHandling %s" % model_name)

        result = list(result)
        answer = moves.input("Delete %s docs? y/n" % len(result))

        if answer == 'y':
            count = 0
            for doc in result:
                if doc.doc_type != model_name:
                    print("Deleted %s docs" % count)
                    raise ValueError("Expected %s, got %s" % (model_name, doc.doc_type))

                doc.delete()
                count += 1

            print("Deleted %s docs" % count)

    def handle(self, **options):
        self.delete_docs(
            'FRIMessageBankMessage',
            FRIMessageBankMessage.view('fri/message_bank', include_docs=True).all()
        )

        self.delete_docs(
            'FRIRandomizedMessage',
            FRIRandomizedMessage.view('fri/randomized_message', include_docs=True).all()
        )

        self.delete_docs(
            'FRIExtraMessage',
            FRIExtraMessage.view('fri/extra_message', include_docs=True).all()
        )

import re
from django.test.testcases import TestCase
from corehq.apps.sms.api import incoming
from corehq.apps.sms.models import SMS, OUTGOING, PhoneNumber
from corehq.apps.sms.util import strip_plus


class TestScript(TestCase):

    def get_last_outbound_sms(self, doc_type, contact_id):
        return SMS.get_last_log_for_recipient(
            doc_type,
            contact_id,
            direction=OUTGOING
        )

    def parse_script(self, script):
        lines = [line.strip() for line in script.split('\n')]
        commands = []
        for line in lines:
            if not line:
                continue
            tokens = re.split(r'([<>])', line, 1)
            phone_number, direction, text = [x.strip() for x in tokens]
            commands.append(
                {
                    'phone_number': phone_number,
                    'direction': direction,
                    'text': text
                }
            )
        return commands

    def run_script(self, script):
        commands = self.parse_script(script)
        for command in commands:
            phone_number = command['phone_number']
            v = PhoneNumber.get_two_way_number(phone_number)
            if command['direction'] == '>':
                incoming(phone_number, command['text'], v.backend_id)
            else:
                msg = self.get_last_outbound_sms(v.owner_doc_type, v.owner_id)
                self.assertEqual(msg.text, str(command['text']))
                self.assertEqual(strip_plus(msg.phone_number), strip_plus(phone_number))
                msg.delete()

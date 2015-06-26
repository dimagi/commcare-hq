from datetime import datetime, timedelta
from django.test import TestCase
from casexml.apps.case.tests import check_xml_line_by_line
from corehq.apps.mobile_auth.utils import new_key_record, get_mobile_auth_payload
from dimagi.ext.jsonobject import HISTORICAL_DATETIME_FORMAT


class MobileAuthTest(TestCase):

    @staticmethod
    def format_datetime_no_usec(dt):
        # phone handler can't deal with microseconds
        return dt.strftime(HISTORICAL_DATETIME_FORMAT)

    def test_xml(self):
        now = datetime.utcnow()
        domain = 'test'
        now_plus_30 = now + timedelta(days=30)
        now_minus_30 = now - timedelta(days=30)
        record = new_key_record(None, None, now=now)
        xml = get_mobile_auth_payload([record], domain, now=now)
        check_xml_line_by_line(self, xml, """
            <OpenRosaResponse xmlns="http://openrosa.org/http/response">
                <message nature="submit_success">Here are your keys!</message>
                <auth_keys domain="{domain}" issued="{now}">
                    <key_record valid="{now}" expires="{now_plus_30}">
                        <uuid>{record.uuid}</uuid>
                        <key type="{record.type}">{record.key}</key>
                    </key_record>
                </auth_keys>
            </OpenRosaResponse>
        """.format(
            now=self.format_datetime_no_usec(now),
            now_plus_30=self.format_datetime_no_usec(now_plus_30),
            record=record,
            domain=domain,
        ))

        record = new_key_record(None, None, now=now, valid=now_minus_30)
        xml = get_mobile_auth_payload([record], domain, now=now)
        check_xml_line_by_line(self, xml, """
            <OpenRosaResponse xmlns="http://openrosa.org/http/response">
                <message nature="submit_success">Here are your keys!</message>
                <auth_keys domain="{domain}" issued="{now}">
                    <key_record valid="{now_minus_30}" expires="{now_plus_30}">
                        <uuid>{record.uuid}</uuid>
                        <key type="{record.type}">{record.key}</key>
                    </key_record>
                </auth_keys>
            </OpenRosaResponse>
        """.format(
            now=self.format_datetime_no_usec(now),
            now_plus_30=self.format_datetime_no_usec(now_plus_30),
            now_minus_30=self.format_datetime_no_usec(now_minus_30),
            record=record,
            domain=domain,
        ))

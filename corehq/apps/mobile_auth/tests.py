from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, timedelta
from django.test import TestCase
from casexml.apps.case.tests.util import check_xml_line_by_line

from corehq.apps.mobile_auth.utils import new_key_record, get_mobile_auth_payload
from dimagi.ext.jsonobject import HISTORICAL_DATETIME_FORMAT
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser


class MobileAuthTest(TestCase):
    def setUp(self):
        self.now = datetime.utcnow()
        self.domain_name = 'test'
        self.domain = create_domain(self.domain_name)
        self.username = 'test-user'
        self.password = 'awesome'
        self.commcare_user = CommCareUser.create(self.domain_name, self.username, self.password)
        self.user_id = self.commcare_user.get_id

    def tearDown(self):
        self.commcare_user.delete()

    @staticmethod
    def format_datetime_no_usec(dt):
        # phone handler can't deal with microseconds
        return dt.strftime(HISTORICAL_DATETIME_FORMAT)

    def test_xml(self):
        now_plus_30 = self.now + timedelta(days=30)
        now_minus_30 = self.now - timedelta(days=30)
        record = new_key_record(None, None, now=self.now)
        xml = get_mobile_auth_payload([record], self.domain_name, now=self.now)
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
            now=self.format_datetime_no_usec(self.now),
            now_plus_30=self.format_datetime_no_usec(now_plus_30),
            record=record,
            domain=self.domain_name,
        ))

        record = new_key_record(None, None, now=self.now, valid=now_minus_30)
        xml = get_mobile_auth_payload([record], self.domain_name, now=self.now)
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
            now=self.format_datetime_no_usec(self.now),
            now_plus_30=self.format_datetime_no_usec(now_plus_30),
            now_minus_30=self.format_datetime_no_usec(now_minus_30),
            record=record,
            domain=self.domain_name,
        ))

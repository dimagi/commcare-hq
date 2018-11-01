# encoding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import doctest
import re
from datetime import datetime

from dateutil.tz import tzutc, tzoffset
from django.test import SimpleTestCase
from lxml import etree

import corehq.motech.openmrs.atom_feed
from corehq.motech.openmrs.atom_feed import get_timestamp, get_patient_uuid


class GetTimestampTests(SimpleTestCase):

    def setUp(self):
        self.feed_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Patient AOP</title>
  <updated>2018-05-15T14:02:08Z</updated>
  <entry>
    <title>Patient</title>
    <updated>2018-04-26T10:56:10Z</updated>
  </entry>
</feed>
"""

    def test_no_node(self):
        xml = re.sub(r'<updated.*</updated>', b'', self.feed_xml)
        feed_elem = etree.XML(xml)
        with self.assertRaisesRegex(ValueError, r'^XPath "./atom:updated" not found$'):
            get_timestamp(feed_elem)

    def test_xpath(self):
        feed_elem = etree.XML(self.feed_xml)
        # "*[local-name()='foo']" ignores namespaces and matches all nodes with tag "foo":
        timestamp = get_timestamp(feed_elem, "./*[local-name()='entry']/*[local-name()='updated']")
        self.assertEqual(timestamp, datetime(2018, 4, 26, 10, 56, 10, tzinfo=tzutc()))

    def test_bad_date(self):
        xml = re.sub(r'2018-05-15T14:02:08Z', b'Nevermore', self.feed_xml)
        feed_elem = etree.XML(xml)
        with self.assertRaisesRegex(ValueError, r'^Unknown string format$'):
            get_timestamp(feed_elem)

    def test_timezone(self):
        xml = re.sub(r'2018-05-15T14:02:08Z', b'2018-05-15T14:02:08+0500', self.feed_xml)
        feed_elem = etree.XML(xml)
        timestamp = get_timestamp(feed_elem)
        self.assertEqual(timestamp, datetime(2018, 5, 15, 14, 2, 8, tzinfo=tzoffset(None, 5 * 60 * 60)))


class GetPatientUuidTests(SimpleTestCase):

    def setUp(self):
        self.feed_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Patient AOP</title>
  <entry>
    <title>Patient</title>
    <content type="application/vnd.atomfeed+xml">
      <![CDATA[/openmrs/ws/rest/v1/patient/e8aa08f6-86cd-42f9-8924-1b3ea021aeb4?v=full]]>
    </content>
  </entry>
</feed>
"""

    def test_no_content_node(self):
        xml = re.sub(r'<content.*</content>', b'', self.feed_xml, flags=re.DOTALL)
        feed_elem = etree.XML(xml)
        entry_elem = next(e for e in feed_elem if e.tag.endswith('entry'))
        with self.assertRaisesRegex(ValueError, r'^patient UUID not found$'):
            get_patient_uuid(entry_elem)

    def test_bad_cdata(self):
        xml = re.sub(r'e8aa08f6-86cd-42f9-8924-1b3ea021aeb4', b'mary-mallon', self.feed_xml)
        feed_elem = etree.XML(xml)
        entry_elem = next(e for e in feed_elem if e.tag.endswith('entry'))
        with self.assertRaisesRegex(ValueError, r'^patient UUID not found$'):
            get_patient_uuid(entry_elem)

    def test_success(self):
        feed_elem = etree.XML(self.feed_xml)
        entry_elem = next(e for e in feed_elem if e.tag.endswith('entry'))
        patient_uuid = get_patient_uuid(entry_elem)
        self.assertEqual(patient_uuid, 'e8aa08f6-86cd-42f9-8924-1b3ea021aeb4')


class DocTests(SimpleTestCase):
    def test_doctests(self):
        results = doctest.testmod(corehq.motech.openmrs.atom_feed)
        self.assertEqual(results.failed, 0)

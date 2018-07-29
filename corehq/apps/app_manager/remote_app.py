from __future__ import absolute_import
from __future__ import unicode_literals
from lxml import etree
import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.urllib.request
from django.urls import reverse
from corehq.apps.app_manager.exceptions import AppEditingError
from corehq.apps.app_manager.xform import WrappedNode
from corehq.apps.users.util import cc_user_domain


class AutoSetVersions(WrappedNode):

    def auto_set_versions(self, version):

        if self.attrib.get('version') == 'auto':
            self_or_empty = [self]
        else:
            self_or_empty = []
        for node in self.findall('.//*[@version="auto"]') + self_or_empty:
            node.attrib['version'] = '%d' % version


class ProfileXML(AutoSetVersions):

    def set_property(self, key, value):
        node = self.find('property[@key="%s"]' % key)

        if node.xml is None:
            node = etree.Element('property')
            self.xml.insert(0, node)
            node.attrib['key'] = key

        node.attrib['value'] = value

    def set_attribute(self, key, value):
        self.attrib[key] = value


def reset_suite_remote_url(suite_node, url_base, profile_url, download_index_url):
    suite_local_text = suite_node.findtext('resource/location[@authority="local"]')
    suite_remote = suite_node.find('resource/location[@authority="remote"]')
    suite_name = strip_location(profile_url, suite_local_text)
    suite_remote.xml.text = url_base + six.moves.urllib.parse.urljoin(download_index_url,
                                                        suite_name)


def strip_location(profile_url, location):
    base = '/'.join(profile_url.split('/')[:-1]) + '/'

    def strip_left(prefix):
        string = location
        if string.startswith(prefix):
            return string[len(prefix):]

    return strip_left('./') or strip_left(base) or strip_left('jr://resource/') or location


def make_remote_profile(app, langs=None):
    try:
        profile = six.moves.urllib.request.urlopen(app.profile_url).read()
    except Exception:
        raise AppEditingError('Unable to access profile url: "%s"' % app.profile_url)

    if app.manage_urls:
        profile_xml = ProfileXML(profile)

        if app.manage_urls:
            profile_xml.auto_set_versions(app.version)
            profile_xml.set_attribute('update', app.hq_profile_url)
            profile_xml.set_property("ota-restore-url", app.ota_restore_url)
            profile_xml.set_property("PostURL", app.post_url)
            profile_xml.set_property("cc_user_domain", cc_user_domain(app.domain))
            profile_xml.set_property('form-record-url', app.form_record_url)
            profile_xml.set_property('key_server', app.key_server_url)
            download_index_url = reverse(
                'download_index',
                args=[app.domain, app.get_id],
            )
            for suite_node in profile_xml.findall('suite'):
                reset_suite_remote_url(
                    suite_node=suite_node,
                    profile_url=app.profile_url,
                    url_base=app.url_base,
                    download_index_url=download_index_url
                )

            if langs:
                profile_xml.set_property("cur_locale", langs[0])

        profile = profile_xml.render()
    return profile


def make_remote_suite(app, suite_xml):
    if app.manage_urls:
        suite = AutoSetVersions(suite_xml)
        suite.auto_set_versions(app.version)
        return suite.render()
    else:
        return suite_xml

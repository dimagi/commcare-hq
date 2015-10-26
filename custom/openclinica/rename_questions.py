#!/usr/bin/env python
from __future__ import absolute_import
import argparse
from collections import defaultdict
from glob import glob
import os
import re
import tempfile
from zipfile import ZipFile
import shutil
from lxml import etree
from custom.openclinica.utils import Item, get_study_metadata


odm_nsmap = {
    'odm': "http://www.cdisc.org/ns/odm/v1.3",
    'OpenClinica': "http://www.openclinica.org/ns/odm_ext_v130/v3.1",
    'OpenClinicaRules': "http://www.openclinica.org/ns/rules/v3.1",
    'xsi': "http://www.w3.org/2001/XMLSchema-instance",
}


def get_item_prefix(form_oid, ig_oid):
    """
    OpenClinica item OIDs are prefixed with "I_<prefix>_" where <prefix> is derived from the item's form OID

    (Dropping "I_<prefix>_" will give us the CommCare question name in upper case)
    """
    form_name = form_oid[2:]  # Drop "F_"
    ig_name = ig_oid[3:]  # Drop "IG_"
    prefix = os.path.commonprefix((form_name, ig_name))
    if prefix.endswith('_'):
        prefix = prefix[:-1]
    return prefix


def read_question_item_map(odm):
    """
    Return a dictionary of {question: (study_event_oid, form_oid, item_group_oid, item_oid)}
    """
    # A dictionary of {question: [(study_event_oid, form_oid, item_group_oid, item_oid)]}
    question_item_map = defaultdict(list)

    meta_e = odm.xpath('./odm:Study/odm:MetaDataVersion', namespaces=odm_nsmap)[0]

    for se_ref in meta_e.xpath('./odm:Protocol/odm:StudyEventRef', namespaces=odm_nsmap):
        se_oid = se_ref.get('StudyEventOID')
        for form_ref in meta_e.xpath('./odm:StudyEventDef[@OID="{}"]/odm:FormRef'.format(se_oid),
                                     namespaces=odm_nsmap):
            form_oid = form_ref.get('FormOID')
            for ig_ref in meta_e.xpath('./odm:FormDef[@OID="{}"]/odm:ItemGroupRef'.format(form_oid),
                                       namespaces=odm_nsmap):
                ig_oid = ig_ref.get('ItemGroupOID')
                prefix = get_item_prefix(form_oid, ig_oid)
                prefix_len = len(prefix) + 3  # len of "I_<prefix>_"
                for item_ref in meta_e.xpath('./odm:ItemGroupDef[@OID="{}"]/odm:ItemRef'.format(ig_oid),
                                             namespaces=odm_nsmap):
                    item_oid = item_ref.get('ItemOID')
                    question = item_oid[prefix_len:].lower()  # Drop prefix
                    question = re.sub(r'^(.*?)_\d+$', r'\1', question)  # Drop OpenClinica-added ID
                    question_item_map[question].append(Item(se_oid, form_oid, ig_oid, item_oid))
    return question_item_map


class CCForm(object):
    nsmap = {
        'h': "http://www.w3.org/1999/xhtml",
        'orx': "http://openrosa.org/jr/xforms",
        'f': "http://www.w3.org/2002/xforms",
        'xsd': "http://www.w3.org/2001/XMLSchema",
        'jr': "http://openrosa.org/javarosa",
        'vellum': "http://commcarehq.org/xforms/vellum",
    }

    def __init__(self, pathname):
        self.pathname = pathname
        self._tree = None
        self.strip_tag_ns_re = re.compile(r'^(?:\{[^}]+})?(.+)$')

    @property
    def name(self):
        filename = self.pathname.split('/')[-1]
        return filename[:-4]  # Strip '.xml'

    @property
    def tree(self):
        if self._tree is None:
            parser = etree.XMLParser(remove_blank_text=True)
            with open(self.pathname) as f:
                for line in f:
                    parser.feed(line)
            self._tree = parser.close()
        return self._tree

    @property
    def _data_element(self):
        instances = self.tree.xpath('./h:head/f:model/f:instance', namespaces=self.nsmap)
        data_nodes = [n for i in instances for n in i]
        return data_nodes[0]

    @property
    def friendly_name(self):
        return self._data_element.get('name')

    @property
    def xmlns(self):
        return self._data_element.nsmap[None]

    def get_questions(self):
        for question_e in self._data_element:
            tag = self.strip_tag_ns_re.match(question_e.tag).group(1)
            if tag not in ('case', 'meta', 'parent'):
                yield tag
                for subquestion_e in question_e.iterdescendants():
                    subtag = self.strip_tag_ns_re.match(subquestion_e.tag).group(1)
                    yield subtag

    def read(self):
        with open(self.pathname) as f:
            return f.read()

    def write(self, string):
        with open(self.pathname, 'w') as f:
            return f.write(string)


class CCModule(object):
    def __init__(self, dirname):
        self.dirname = dirname

    @property
    def name(self):
        return self.dirname.split('/')[-1]

    def get_forms(self):
        for form_pathname in glob(self.dirname + '/forms-*.xml'):
            yield CCForm(form_pathname)


class CCZFile(object):
    def __init__(self, pathname):
        self.pathname = pathname

    def __enter__(self):
        self.dirname = tempfile.mkdtemp()
        with ZipFile(self.pathname) as ccz_file:
            ccz_file.extractall(self.dirname)
        return self

    def get_modules(self):
        for module_dirname in glob(self.dirname + '/modules-*'):
            yield CCModule(module_dirname)

    def __exit__(self, exc_type, exc_val, exc_tb):
        # shutil.rmtree(self.dirname)
        print 'Changes can be found in ', self.dirname


def replace_question(question, item, string):
    pattern = re.compile(r'\b{}\b'.format(question))
    repl = item.item_oid.lower()
    return pattern.sub(repl, string)


def rename_questions(ccz_pathname, question_item_map):
    x = n = m = 0
    with CCZFile(ccz_pathname) as ccz_file:
        for ccmodule in ccz_file.get_modules():
            if ccmodule.name in ('modules-0', 'modules-1', 'modules-8'):
                # CommCare-only module
                continue
            elif ccmodule.name == 'modules-6':
                last_event = 'SE_VISIT2EVENT'
            elif ccmodule.name == 'modules-8':
                last_event = 'SE_ENDOFSTUDY'
            elif ccmodule.name == 'modules-13':
                last_event = 'SE_UNSCHEDULEDVISIT'
            else:
                last_event = None
            for ccform in ccmodule.get_forms():
                string = ccform.read()
                changed = False
                for question in ccform.get_questions():
                    n += 1
                    if question in question_item_map:
                        m += 1
                        items = question_item_map[question]
                        if not len(items):
                            # question not in OpenClinica
                            continue
                        elif len(items) == 1:
                            x += 1
                            string = replace_question(question, items[0], string)
                            changed = True
                            if not last_event:
                                last_event = items[0].study_event_oid
                        else:
                            if last_event:
                                # Try to guess
                                guesses = [i for i in items if i.study_event_oid == last_event]
                                if len(guesses) == 1:
                                    x += 1
                                    string = replace_question(question, guesses[0], string)
                                    changed = True
                                    continue
                            print 'Question "{}" in {}/{}.xml could be any of {}'.format(
                                question, ccmodule.name, ccform.name, ', '.join([i.item_oid for i in items]))
                if changed:
                    # last_event is set if string has been changed. Save it.
                    ccform.write(string)
    print 'Changed {} of {} OpenClinica items, of {} CommCare questions'.format(x, m, n)


def main(ccz):
    domain = 'kemri'
    metadata_xml = get_study_metadata(domain)
    map_ = read_question_item_map(metadata_xml)
    print 'There are {} OpenClinica items'.format(sum([len(v) for v in map_.values()]))
    rename_questions(ccz, map_)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('ccz', action='store')
    args = parser.parse_args()
    main(args.ccz)

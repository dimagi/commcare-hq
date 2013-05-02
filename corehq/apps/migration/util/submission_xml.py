from lxml import etree
import functools
from sys import stdin

def get_xmlns(el):
    return el.tag.split('}')[0][1:]

def get_subnode(el, name):
    # the following way seems to work only (deterministically) non-deterministically: WTF!?
    # return el.find('m:{name}'.format(name=name), namespaces={'m': get_xmlns(el)})
    # the following seems to work ALL the time
    return el.find('{%s}%s' % (get_xmlns(el), name))

def map_text(el, fn):
    if el is not None:
        el.text = fn(el.text)

def findall(el, xpath):
    return el.findall(xpath.format(m=get_xmlns(el)))

def dict_to_function(map):
    if hasattr(map, '__call__'):
        return map
    else:
        return lambda x: map.get(x, x)

class dict_or_function(object):
    def __init__(self, position):
        self.position = position

    def __call__(self, fn):
        @functools.wraps(fn)
        def decorated(*args, **kwargs):
            args = list(args)
            args[self.position] = dict_to_function(args[self.position])
            return fn(*args, **kwargs)
        return decorated

class IdMap(object):
    def __init__(self, salt):
        self.salt = salt

    def __call__(self, old_id):
        import hashlib
        return hashlib.sha1(self.salt + ' ' + old_id).hexdigest()

class SubmissionXML(object):
    namespaces = {
        'orx': "http://openrosa.org/jr/xforms",
        'cx2': "http://commcarehq.org/case/transaction/v2",
    }

    def __init__(self, xml):
        self.root = etree.ElementTree(etree.fromstring(xml))
        namespaces = {}
        namespaces.update(self.namespaces)
        self.namespaces = namespaces
        self.namespaces['x'] = get_xmlns(self.root.getroot())

    def get_meta(self):
        metas = []
        for xpath in ('{{{orx}}}meta', '{{{x}}}meta', '{{{orx}}}Meta', '{{{x}}}Meta'):
            metas.extend(self.root.findall(xpath.format(**self.namespaces)))
        return metas

    def get_cases1(self):
        return self.root.findall('//{{{x}}}case'.format(**self.namespaces))

    def get_cases2(self):
        return self.root.findall('//{{{cx2}}}case'.format(**self.namespaces))

    @dict_or_function(1)
    def replace_form_id(self, form_id_map):
        for meta_node in self.get_meta():
            for INSTANCE_ID in ('instanceID', 'uid'):
                node = get_subnode(meta_node, INSTANCE_ID)
                map_text(node, form_id_map)


    @dict_or_function(1)
    def replace_user_id(self, user_id_map):
        for meta_node in self.get_meta():
            for USER_ID in ('userID', 'chw_id'):
                node = get_subnode(meta_node, USER_ID)
                map_text(node, user_id_map)

        for node in self.get_cases2():
            node.attrib['user_id'] = user_id_map(node.attrib['user_id'])

        for node in self.get_cases1():
            node = get_subnode(node, 'user_id')
            map_text(node, user_id_map)

    @dict_or_function(1)
    def replace_case_id(self, case_id_map):
        for case_node in self.get_cases2():
            case_node.attrib['case_id'] = case_id_map(case_node.attrib['case_id'])
            for index in case_node.findall('{{{cx2}}}index/{{{cx2}}}*'.format(**self.namespaces)):
                map_text(index, case_id_map)
        for case_node in self.get_cases1():
            case_id_node = get_subnode(case_node, 'case_id')
            map_text(case_id_node, case_id_map)

    @dict_or_function(1)
    def replace_owner_id(self, owner_id_map):
        for case_node in self.get_cases1() + self.get_cases2():
            owner_id_nodes = findall(case_node, '{{{m}}}create/{{{m}}}owner_id') + findall(case_node, '{{{m}}}update/{{{m}}}owner_id')
            for owner_id_node in owner_id_nodes:
                map_text(owner_id_node, owner_id_map)

    def prepare_for_resubmission(self, user_id_map, owner_id_map, salt):
        id_map = IdMap(salt)
        self.replace_user_id(user_id_map)
        self.replace_owner_id(owner_id_map)
        self.replace_form_id(id_map)
        self.replace_case_id(id_map)

    def tostring(self):
        return etree.tostring(self.root)


def prepare_for_resubmission(xml, user_id_map, owner_id_map, salt):
    s = SubmissionXML(xml)
    s.prepare_for_resubmission(user_id_map, owner_id_map, salt)
    return s.tostring()

if __name__ == '__main__':
    xml = stdin.read()
    print prepare_for_resubmission(xml, lambda x: 'NEW-USER-ID', lambda x: 'NEW-OWNER-ID', 'salty!')
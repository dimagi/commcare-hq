import sys, os
import re
import json
from corehq.apps.users.util import normalize_username

def get_username(xml):
    try:
        username = re.search(r'<[Mm]eta>.*<username>(.*)</username>.*</[Mm]eta>', xml).group(1)
        return normalize_username(username)
    except:
        return None

def get_chw_id(xml):
    try:
        return re.search(r'<[Mm]eta>.*<chw_id>(.......*)</chw_id>.*</[Mm]eta>', xml).group(1)
    except:
        return None
        
def get_userID(xml):
    "find the userID after calling replace_userID"
    try:
        return re.search(r'<[Mm]eta>.*<userID>(.*)</userID>.*</[Mm]eta>', xml).group(1)
    except:
        None

def replace_user_id(xml, user_id):
    if not user_id:
        user_id = ""
    # in meta block
    user_id_re = r'(<[Mm]eta>.*<userid>)(.*)(</userid>.*</[Mm]eta>)'
    if re.search(user_id_re, xml):
        xml = re.sub(user_id_re, r'\g<1>%s\g<3>' % user_id, xml)
    else:
        xml = re.sub(r'(<[Mm]eta>.*)(<username>.*</username>)(.*</[Mm]eta>)', r"\1\2<userID>%s</userID>\3" % user_id, xml)
    # in case block
    user_id_re = r'(<case>.*<user_id>)(.*)(</user_id>.*</case>)'
    if re.search(user_id_re, xml):
        xml = re.sub(user_id_re, r'\g<1>%s\g<3>' % user_id, xml)
    return xml
    
def add_user_id(xml, user_map):
    username = get_username(xml)
    user_id = user_map.get(username, None)
    if not user_id:
        print "Not in usermap: %s" % username
    return replace_user_id(xml, user_id)
    
    

if __name__ == "__main__":
    user_regs = sys.argv[1]
    domain = sys.argv[2]
    with open(user_regs) as f:
        user_map = json.load(f)
    xml = sys.stdin.read()
    print add_user_id(xml, user_map[domain])
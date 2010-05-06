'''
Utility of xml stuff.
'''

def get_tag(xmlns, tag):
    # this is odd, but our python xml libraries seem to want to name things like:
    # {http://www.commcarehq.org/backup}sometag
    return "{%s}%s" % (xmlns, tag)
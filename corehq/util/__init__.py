import re

from .view_utils import reverse


def fix_urls(text):
    """
    Wraps urls in a string with anchor tags
    http://stackoverflow.com/questions/1071191/detect-urls-in-a-string-and-wrap-with-a-href-tag#answer-1071240
    """
    pat_url = re.compile(  r'''
                     (?x)( # verbose identify URLs within text
         (http|ftp|gopher) # make sure we find a resource type
                       :// # ...needs to be followed by colon-slash-slash
            (\w+[:.]?){2,} # at least two domain groups, e.g. (gnosis.)(cx)
                      (/?| # could be just the domain name (maybe w/ slash)
                [^ \n\r"]+ # or stuff then space, newline, tab, quote
                    [\w/]) # resource name ends in alphanumeric or slash
         (?=[\s\.,>)'"\]]) # assert: followed by white or clause ending
                         ) # end of match group
                           ''')
    pat_email = re.compile(r'''
                    (?xm)  # verbose identify URLs in text (and multiline)
                 (?=^.{11} # Mail header matcher
         (?<!Message-ID:|  # rule out Message-ID's as best possible
             In-Reply-To)) # ...and also In-Reply-To
                    (.*?)( # must grab to email to allow prior lookbehind
        ([A-Za-z0-9-]+\.)? # maybe an initial part: DAVID.mertz@gnosis.cx
             [A-Za-z0-9-]+ # definitely some local user: MERTZ@gnosis.cx
                         @ # ...needs an at sign in the middle
              (\w+\.?){2,} # at least two domain groups, e.g. (gnosis.)(cx)
         (?=[\s\.,>)'"\]]) # assert: followed by white or clause ending
                         ) # end of match group
                           ''')

    for url in re.findall(pat_url, text):
       text = text.replace(url[0], '<a href="%(url)s">%(url)s</a>' % {"url" : url[0]})

    for email in re.findall(pat_email, text):
       text = text.replace(email[1], '<a href="mailto:%(email)s">%(email)s</a>' % {"email" : email[1]})

    return text


def remove_dups(list_of_dicts, unique_key):
    keys = set([])
    ret = []
    for d in list_of_dicts:
        if d.get(unique_key) not in keys:
            keys.add(d.get(unique_key))
            ret.append(d)
    return ret

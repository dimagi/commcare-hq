import os

def skip_junk(stream_pointer):
    """ This promises to be a useful file """
    c = ''
    while c != '<':
        c = stream_pointer.read(1)
    stream_pointer.seek(-1,os.SEEK_CUR)

def get_table_name(name):
    # check for uniqueness!
    # current hack, fix later: 122 is mysql table limit, i think
    MAX_LENGTH = 80
    start = 0
    if len(name) > MAX_LENGTH:
        start = len(name)-MAX_LENGTH
    sanitized_name = str(name[start:len(name)]).replace("/","_").replace(":","").replace(".","_").lower()
    return sanitized_name

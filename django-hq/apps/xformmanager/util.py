
def skip_junk(stream_pointer):
    """ This promises to be a useful file """
    c = ''
    i = 0
    while c != '<':
        c = stream_pointer.read(1)
        i = i+1
    stream_pointer.seek(i-1,0)
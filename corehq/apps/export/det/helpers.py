

def collapse_path_out(path, relative=''):
    return collapse_path(path, relative, 0)


def collapse_path(path, relative='', s=0):
    if relative:
        return '.'.join(
            [
                p['name']+'[*]' if p['is_repeat'] else p['name'] for p in path[s:]
            ]).replace(relative+'.','',1)
    return '.'.join(
        [
            p['name']+'[*]' if p['is_repeat'] else p['name'] for p in path[s:]
        ])


def prepend_prefix(path, default_prefix):
    if not path.startswith(default_prefix):
        return '{}{}'.format(default_prefix, path)
    return path


def truncate(name, start_char, total_char):
    if len(name) > total_char:
        name = name[:start_char] + '$' + name[-(total_char-(start_char+1)):]
    return name

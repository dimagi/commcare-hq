def file_extention_from_filename(filename):
    extension = filename.rsplit('.', 1)[-1]
    if extension:
        return '.{}'.format(extension)
    return ''

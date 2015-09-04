def file_extention_from_filename(filename):
    return '.{}'.format(filename.rsplit('.', 1)[-1])

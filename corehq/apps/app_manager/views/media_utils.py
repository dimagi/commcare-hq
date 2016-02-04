def process_media_attribute(attribute, resp, val):
    if val:
        val = interpolate_media_path(val)
        resp['corrections'][attribute] = val
    else:
        val = None
    return val


def interpolate_media_path(val):
    if not val:
        return val

    if val.startswith('jr://'):
        pass
    elif val.startswith('/file/'):
        val = 'jr:/' + val
    elif val.startswith('file/'):
        val = 'jr://' + val
    elif val.startswith('/'):
        val = 'jr://file' + val
    else:
        val = 'jr://file/' + val

    return val


def handle_media_edits(request, item, should_edit, resp, lang):
    if 'corrections' not in resp:
        resp['corrections'] = {}
    for attribute in ('media_image', 'media_audio'):
        if should_edit(attribute):
            media_path = process_media_attribute(attribute, resp, request.POST.get(attribute))
            item._set_media(attribute, lang, media_path)

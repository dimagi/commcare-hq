from __future__ import unicode_literals


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


def handle_media_edits(request, item, should_edit, resp, lang, prefix=''):
    if 'corrections' not in resp:
        resp['corrections'] = {}

    for attribute in ('media_image', 'media_audio'):
        param = prefix + attribute
        if should_edit(param):
            media_path = process_media_attribute(param, resp, request.POST.get(param))
            item._set_media(attribute, lang, media_path)

    for attribute in ('use_default_image_for_all', 'use_default_audio_for_all'):
        param = prefix + attribute
        if should_edit(param):
            setattr(item, attribute, request.POST.get(param) == 'true')

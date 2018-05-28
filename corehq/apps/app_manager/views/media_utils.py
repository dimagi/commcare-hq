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


def handle_media_edits(request, item, should_edit, resp, lang, app):
    if 'corrections' not in resp:
        resp['corrections'] = {}
    for attribute in ('media_image', 'media_audio'):
        if should_edit(attribute):
            old_value = getattr(item, attribute, {}).get(lang, None)
            media_path = process_media_attribute(attribute, resp, request.POST.get(attribute))
            item._set_media(attribute, lang, media_path)
            # remove the entry from app multimedia mappings if media is being removed now
            # This does not remove the multimedia but just it's reference in mapping
            if old_value and not media_path:
                app.multimedia_map.pop(old_value, None)

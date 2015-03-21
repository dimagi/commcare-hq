from corehq.apps.programs.models import Program


def ews_smsuser_extension(sms_user, user):
    sms_user.user_data['to'] = user.to
    if user.family_name != '':
        sms_user.last_name = user.family_name

    sms_user.save()
    return sms_user


def ews_webuser_extension(couch_user, user):
    couch_user.user_data['sms_notifications'] = user.sms_notifications
    couch_user.user_data['organization'] = user.organization
    couch_user.save()
    return couch_user


def ews_location_extension(location, loc):
    location.metadata['created_at'] = loc.created_at
    location.metadata['supervised_by'] = loc.supervised_by
    location.save()
    return location


def ews_product_extension(couch_product, product):
    if not product.program.code:
        return couch_product
    program = Program.get_by_code(couch_product.domain, product.program.code)
    if not program:
        program = Program(domain=couch_product.domain)
        program.name = product.program.name
        program.code = product.program.code.lower()
        program._doc_type_attr = "Program"
        program.save()
    if couch_product.program_id != program._id:
        couch_product.program_id = program._id
        couch_product.save()

    return couch_product

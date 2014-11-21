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

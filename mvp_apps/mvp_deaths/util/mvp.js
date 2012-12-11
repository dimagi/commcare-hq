var MS_IN_DAY = 24*60*60*1000;

function hasIndicators(doc) {
    return (doc.computed_ && doc.computed_.mvp_indicators);
}

function isChildRegistrationForm(doc) {
    return (doc.doc_type === "XFormInstance"
        && doc.xmlns === 'http://openrosa.org/formdesigner/E6511C2B-DFC8-4DEA-8200-CC2F2CED00DA'
        && hasIndicators(doc));
}

function isChildVisitForm(doc) {
    return (doc.doc_type === "XFormInstance"
        && doc.xmlns === 'http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A'
        && hasIndicators(doc));
}

function isChildCloseForm(doc) {
    return (doc.doc_type === "XFormInstance"
        && doc.xmlns === 'http://openrosa.org/formdesigner/AC164B28-AECA-45C9-B7F6-E0668D5AF84B'
        && hasIndicators(doc));
}

function isPregnancyVisitForm(doc) {
    return (doc.doc_type === "XFormInstance"
        && doc.xmlns === 'http://openrosa.org/formdesigner/185A7E63-0ECD-4D9A-8357-6FD770B6F065'
        && hasIndicators(doc));
}

function isPregnancyCloseForm(doc) {
    return (doc.doc_type === "XFormInstance"
        && doc.xmlns === 'http://openrosa.org/formdesigner/01EB3014-71CE-4EBE-AE34-647EF70A55DE'
        && hasIndicators(doc));
}

function isHomeVisitForm(doc) {
    return (doc.doc_type === "XFormInstance"
        && doc.xmlns === 'http://openrosa.org/formdesigner/266AD1A0-9EAE-483E-B4B2-4E85D6CA8D4B'
        && hasIndicators(doc));
}

function isDeathWithoutRegistrationForm(doc) {
    return (doc.doc_type === "XFormInstance"
        && doc.xmlns === 'http://openrosa.org/formdesigner/b3af1fddeb661ee045fef1e764995440ea8f057f'
        && hasIndicators(doc));
}

function isHouseholdCase(doc) {
    return (doc.doc_type === "CommCareCase"
        && doc.type === 'household');
}

function isChildCase(doc) {
    return (doc.doc_type === "CommCareCase"
        && doc.type === 'child');
}

function isPregnancyCase(doc) {
    return (doc.doc_type === "CommCareCase"
        && doc.type === 'pregnancy');
}

function get_indicators(doc) {
    if (doc.computed_ && doc.computed_.mvp_indicators) {
        return doc.computed_.mvp_indicators;
    }
    return {};
}

function get_user_id(doc) {
    if (doc.doc_type === 'XFormInstance') {
        return doc.form.meta.userID;
    }
    return doc.user_id;
}

function get_case_id(doc) {
    if (doc.doc_type === 'XFormInstance') {
        return doc.form['case']['@case_id'];
    }
    return doc._id;
}

function get_date_key(date) {
    var year = date.getUTCFullYear(),
        month = date.getUTCMonth()+1,
        day = date.getUTCDate();
    return [year, month, day];
}

function smart_date_emit_key(prefix, date, suffix, trim_date) {
    var emit_key = prefix.slice(0);

    var date_key = get_date_key(date);
    if (!isNaN(trim_date)) {
        var trimmed_date_key = [trim_date];
        for(var t = 0; t<=trim_date; t++) {
            trimmed_date_key.push(date_key[t]);
        }
        date_key = trimmed_date_key;
    }
    emit_key.push.apply(emit_key, date_key);

    if (suffix) {
        emit_key.push.apply(emit_key, suffix);
    }
    return emit_key;
}

function get_pregnancy_start_from_edd_date(edd_date) {
    var preg_start = new Date(),
        gestation_ms = 266*MS_IN_DAY;
    var start_ms = edd_date.getTime() - gestation_ms;
    preg_start.setTime(start_ms);
    return preg_start;
}

function get_danger_signs(danger_sign_value) {
    if (danger_sign_value) {
        var signs = danger_sign_value.trim().toLowerCase();
        signs = signs.split(' ');
        return signs;
    }
    return [];
}

function get_age_from_dob(dob, date_diff) {
    // dob and date_diff are date strings
    var now,
        birth_date = new Date(dob);
    if (date_diff) {
        now = new Date(date_diff);
    } else {
        now = new Date();
    }
    if (now >= birth_date) {
        return (now.getTime() - birth_date.getTime())/(MS_IN_DAY*365);
    }
    return null;
}

function contained_in_indicator_value(indicator, text) {
    if (indicator && indicator.value) {
        return (indicator.value.toLowerCase().indexOf(text) >= 0);
    }
    return false;
}

function emit_standard(doc, emit_date, indicator_keys, suffix) {
    var user_id = get_user_id(doc);
    for (var k = 0; k < indicator_keys.length; k++) {
        emit(smart_date_emit_key(["all", doc.domain, indicator_keys[k]], emit_date, suffix), 1);
        emit(smart_date_emit_key(["user", doc.domain, user_id, indicator_keys[k]], emit_date, suffix), 1);
    }
}

function emit_special(doc, emit_date, indicator_entries, suffix) {
    var user_id = get_user_id(doc);
    for (var key in indicator_entries) {
        if (indicator_entries.hasOwnProperty(key)) {
            var entry = indicator_entries[key];
            emit(smart_date_emit_key(["all", doc.domain, key], emit_date, suffix), entry);
            emit(smart_date_emit_key(["user", doc.domain, user_id, key], emit_date, suffix), entry);
        }
    }
}

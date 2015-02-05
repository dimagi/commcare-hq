var MS_IN_DAY = 24*60*60*1000;

function hasIndicators(doc) {
    return (doc.computed_ && doc.computed_.mvp_indicators);
}

function hasFormLabel(doc, label_name) {
    return (hasIndicators(doc) && 
        label_name in doc.computed_.mvp_indicators && 
        doc.computed_.mvp_indicators[label_name].type === "FormLabelIndicatorDefinition");
}

function isVerbalAutopsyNeonateForm(doc) {
    return (doc.doc_type === "IndicatorXForm" && hasFormLabel(doc, "verbal_autopsy_neonate_form"));
}

function isVerbalAutopsyChildForm(doc) {
    return (doc.doc_type === "IndicatorXForm" && hasFormLabel(doc, "verbal_autopsy_child_form"));
}

function isVerbalAutopsyAdultForm(doc) {
    return (doc.doc_type === "IndicatorXForm" && hasFormLabel(doc, "verbal_autopsy_adult_form"));
}

function get_indicators(doc) {
    if (doc.computed_ && doc.computed_.mvp_indicators) {
        return doc.computed_.mvp_indicators;
    }
    return {};
}

function get_user_id(doc) {
    if (doc.doc_type === 'IndicatorXForm') {
        return doc.form.meta.userID;
    }
    return doc.owner_id || doc.user_id;
}

function get_case_id(doc) {
    if (doc.doc_type === 'IndicatorXForm') {
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

function get_age_from_dob(dob, date_diff) {
    // dob and date_diff are date strings
    try {
        var now = new Date(date_diff),
            birth_date = new Date(dob);
        if (now >= birth_date) {
            return now.getTime() - birth_date.getTime();
        }
    } catch (e) {
        // do nothing
    }
    return null;
}

function contained_in_indicator_value(indicator, text) {
    try {
        return (indicator.value.toLowerCase().indexOf(text) >= 0);
    } catch (e) {
        // do nothing
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

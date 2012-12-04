var MS_IN_DAY = 24*60*60*1000;

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
    var emit_key = new Array();
    emit_key.push.apply(emit_key, prefix);

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

function emit_standard(doc, emit_date, indicator_keys, suffix) {
    var user_id = get_user_id(doc);
    for (var k in indicator_keys) {
        emit(smart_date_emit_key(["all", doc.domain, doc.type, indicator_keys[k]], emit_date, suffix), 1);
        emit(smart_date_emit_key(["user", doc.domain, doc.type, user_id, indicator_keys[k]], emit_date, suffix), 1);
    }
}

function emit_special(doc, emit_date, indicator_entries, suffix) {
    var user_id = get_user_id(doc);
    for (var key in indicator_entries) {
        var entry = indicator_entries[key];
        emit(smart_date_emit_key(["all", doc.domain, doc.type, key], emit_date, suffix), entry);
        emit(smart_date_emit_key(["user", doc.domain, doc.type, user_id, key], emit_date, suffix), entry);
    }
}

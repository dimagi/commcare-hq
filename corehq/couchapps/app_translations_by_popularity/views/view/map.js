function (doc) {
    if (doc.doc_type === 'Application' && doc.copy_of === null) {
        var lang, key;
        for (lang in doc.translations) {
            for (key in doc.translations[lang]) {
                emit([lang, key, doc.translations[lang][key]], null);
            }
        }
    }
}

function (doc) {
    if ((doc.doc_type === 'Application' && doc.copy_of === null) || doc.doc_type === 'TranslationDoc') {
        var lang, key, weight = (doc.doc_type === 'Application') ? 1 : 0;
        for (lang in doc.translations) {
            for (key in doc.translations[lang]) {
                emit([lang, key, doc.translations[lang][key]], weight);
            }
        }
    }
}
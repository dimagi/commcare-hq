function (doc) {
    var key, t, types = ['properties', 'features'];
    if (doc.doc_type === 'Application' && !doc.copy_of) {
        for (i = 0; i < types.length; i += 1) {
            for (key in doc.profile[types[i]]) {
                if (doc.profile[types[i]].hasOwnProperty(key)) {
                    emit([types[i], key, doc.profile.properties[key]], null);
                }
            }
        }
    }
}
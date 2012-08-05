function(doc) {
//    try {
    if (doc.doc_type === 'CommCareAudio' && doc.shared_by && doc.shared_by.length > 0)
    {
        var ret = new Document();
        doc.shared_by.forEach(function(domain) {
            if (doc.tags[domain] && doc.tags[domain].length > 0) {
                doc.tags[domain].forEach(function (tag) {
                    ret.add(tag);
                });
            }

            ret.add(doc.licenses[domain]);
            ret.add({
                'public': 'Public Domain',
                'cc': 'Creative Commons Attribution',
                'cc-sa': 'Creative Commons Attribution, Share Alike',
                'cc-nd': 'Creative Commons Attribution, No Derivatives',
                'cc-nc': 'Creative Commons Attribution, Non-Commercial',
                'cc-nc-sa': 'Creative Commons Attribution, Non-Commercial, and Share Alike',
                'cc-nc-nd': 'Creative Commons Attribution, Non-Commercial, and No Derivatives'
            }[doc.licenses[domain]]); // directly copied from models.py. Be sure to update--for now just a hack.
        })

        return ret;
    }
/*    }
    catch (err) {
        // lucene may not be configured, do nothing
    }*/

}
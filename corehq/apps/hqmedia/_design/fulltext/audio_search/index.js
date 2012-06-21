function(doc) {
//    try {
        if (doc.doc_type === 'CommCareAudio' && doc.shared)
        {
            var ret = new Document();
            if (doc.tags && doc.tags.length > 0) {
                doc.tags.forEach(function (tag) {
                    ret.add(tag);
                });
            }

            ret.add(doc.title);
            if (doc.filenames && doc.filenames.length > 0) {
                doc.filenames.forEach(function(filename) {
                    ret.add(filename.replace('/', ' ').replace('_', ' '));
                });
            }

            ret.add(doc.license);
            ret.add({
                        'public': 'Public Domain',
                        'cc': 'Creative Commons Attribution',
                        'cc-sa': 'Creative Commons Attribution, Share Alike',
                        'cc-nd': 'Creative Commons Attribution, No Derivatives',
                        'cc-nc': 'Creative Commons Attribution, Non-Commercial',
                        'cc-nc-sa': 'Creative Commons Attribution, Non-Commercial, and Share Alike',
                        'cc-nc-nd': 'Creative Commons Attribution, Non-Commercial, and No Derivatives'
                    }[doc.license]); // directly copied from models.py. Be sure to update--for now just a hack.

            return ret;
        }
/*    }
    catch (err) {
        // lucene may not be configured, do nothing
    }*/

}
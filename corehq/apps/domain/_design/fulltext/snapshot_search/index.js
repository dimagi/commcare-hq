function(doc) {
//    try {
        if (doc.doc_type == "Domain" && doc.is_snapshot && doc.published && doc.is_approved)
        {
            var ret = new Document();
//            ret.add(doc.original_doc);
            ret.add(doc.description);
            ret.add(doc.organization);
            ret.add(doc.title);
            ret.add(doc.author);
            ret.add(doc.phone_model);
            ret.add({
                        'public': 'Public Domain',
                        'cc': 'Creative Commons Attribution',
                        'cc-sa': 'Creative Commons Attribution, Share Alike',
                        'cc-nd': 'Creative Commons Attribution, No Derivatives',
                        'cc-nc': 'Creative Commons Attribution, Non-Commercial',
                        'cc-nc-sa': 'Creative Commons Attribution, Non-Commercial, and Share Alike',
                        'cc-nc-nd': 'Creative Commons Attribution, Non-Commercial, and No Derivatives'
                    }[doc.license]); // directly copied from models.py. Be sure to update--for now just a hack.

            ret.add(doc.license);
            ret.add(doc.project_type);
            ret.add(doc.license, {'field': 'license'});
            ret.add(doc.organization, {'field': 'organization'});
            ret.add(doc.project_type, {'field': 'category'});
            ret.add(doc.author, {'field': 'author'});

            return ret;
        }
/*    }
    catch (err) {
        // lucene may not be configured, do nothing
    }*/

}
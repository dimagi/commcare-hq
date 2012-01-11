function(doc) {
    try {
        if (doc.doc_type == "CommCareCase")
        {
            var ret = new Document(); 
            ret.add(doc.name, {"field": "default"});
            ret.add(doc.name, {"field": "name"});
            ret.add(doc.opened_on, {"field": "opened"}); 
            ret.add(doc.modified_on, {"field": "modified"});
            ret.field('sort_mod_date',  doc.modified_on,  'yes', 'not_analyzed');
            ret.add(doc.domain, {"field": "domain"});
            ret.add(doc.user_id, {"field": "user_id"});
            ret.add(doc.type, {"field": "type"});
            if (doc.closed) {
                ret.add("closed", {"field": "is"});
                ret.add(doc.closed_on, {"field": "closed"}); 
            } else {
                ret.add("open", {"field": "is"});
            } 
            
            return ret;
        }
    }
    catch (err) {
        // lucene may not be configured, do nothing
    }
    
}
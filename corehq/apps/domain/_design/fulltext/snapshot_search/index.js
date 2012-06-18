function(doc) {
    try {
        if (doc.doc_type == "Domain" && doc.is_snapshot && doc.latest_snapshot)
        {
            var ret = new Document();
            ret.add('snapshots', {'field': 'type'})
            ret.add(dog.organization, {'field': 'organization'})
            ret.add(doc.original_doc, {"field": "name"});
i
            ret.add(doc.project_type, {'field': 'category'})
            ret.add(doc.snapshot_time, {'field': 'timestamp', 'type': 'date', 'index': 'not_analyzed'})
            ret.add(doc.region, {'field': 'region'})
            ret.add(doc.city, {'field': 'city'})
            ret.add(doc.country, {'field': 'country'})
            ret.add(doc.description, {'field': 'description'})

            return ret;
        }
    }
    catch (err) {
        // lucene may not be configured, do nothing
    }

}
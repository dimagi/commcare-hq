function(doc) {
    try {
        if (doc.doc_type == "Domain" && doc.is_snapshot && doc.latest_snapshot)
        {
            var ret = new Document();
            ret.add('snapshots', {'field': 'type'})
            if (doc.organization) { // eventually we should only allow snapshots of projects in organizations
                ret.add(doc.slug, {"field": "name"});
                ret.add(dog.organization, {'field': 'organization'})
            } else {
                ret.add(doc.name, {"field": "name"});
            }

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
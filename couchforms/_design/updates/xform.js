function(doc, req) {
    var e4xmlJsonClass = require("util/jsone4xml").e4xmlJsonClass;
    var base64Class = require("util/base64").Base64;
    var dateFormat = require("util/dateFormat").dateFormat;

    if (doc) {
        log("doc wasn't null!  this is unexpected! you will LOSE your information in favor of the xml");
    }
    // Workaround: Mozilla Bug 336551
    // see https://developer.mozilla.org/en-US/docs/E4X
    // NOTE: the regex on that page is no longer valid so replaced with the one from the following:
    // https://bugzilla.mozilla.org/show_bug.cgi?id=336551#c24
    var content = req.body.replace(/<\?xml[^>]*\?>/, "");
    var xml_content = new XML(content);
    doc = {};
    doc['form'] = e4xmlJsonClass.xml2obj(xml_content);
        
    // Because there is an xmlns in the form we can't reference these normally 
    // like .uuid therefore we have to use the *:: annotation, which searches 
    // every namespace.
    // See: http://dispatchevent.org/roger/using-e4x-with-xhtml-watch-your-namespaces/
    var getUuid = function(form) {
        // search for a uuid in some known places
        
        // this is when it's overridden in the query string (e.g. a duplicate)
        if (req.query && req.query.uid) return req.query.uid;
        
        // this is super hacky, but here are some known places we keep this 
        // in some known deployments
        meta = null;
        if (form.Meta) meta = form.Meta;  // bhoma, 0.9 commcare
        else if (form.meta) meta = form.meta; // commcare 1.0
        if (meta && meta.uid) return meta.uid; // bhoma 
        if (meta && meta.instanceID) return meta.instanceID; // commcare 0.9, commcare 1.0
        
        var guid = function() {
            // http://stackoverflow.com/questions/105034/how-to-create-a-guid-uuid-in-javascript
            // TODO: find a better guid generator / plug into couch uuid framework
            var S4 = function() { 
                return (((1+Math.random())*0x10000)|0).toString(16).substring(1);
            }
            return (S4()+S4()+S4()+S4()+S4()+S4()+S4()+S4());   
        }
        return guid();
    }
    
    // Try to get an id from the form, or fall back to generating one randomly
    uuid = getUuid(doc.form);
    doc["_id"] = uuid.toString();
    
    // attach the raw xml as a file called "form.xml"
    // This has to be base64 encoded to store properly in couch.
    var attachments = { "form.xml" : { "content_type":"text/xml", "data": base64Class.encode(req.body) } };      
    doc["_attachments"] = attachments;
    
    doc["doc_type"] = "XFormInstance";
    // This magic tag lets our xforms be exportable by namespace from the couchexport app
    doc["#export_tag"] = "xmlns";
    doc["xmlns"] = doc.form['@xmlns'];
    doc["received_on"] = dateFormat(Date(), "isoUtcDateTime");


    var resp =  {"headers" : {"Content-Type" : "text/plain"},
                 "body" : uuid.toString()};
    return [doc, resp];
}


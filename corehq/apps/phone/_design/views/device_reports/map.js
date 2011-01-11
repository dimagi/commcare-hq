function(doc) { 
    XMLNS = "http://code.javarosa.org/devicereport";
    if (doc["#doc_type"] == "XForm" && doc["@xmlns"]==XMLNS) {
        date = new Date(doc.report_date);
        emit([doc.device_id, date], doc);
    }
}
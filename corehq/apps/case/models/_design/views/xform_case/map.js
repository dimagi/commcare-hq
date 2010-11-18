function(doc) {
    /** Lists cases that are found in xforms **/
    if (doc["#doc_type"] == "XForm" && doc["#patient_id"]) {
        // TODO: make this recursive
        if (doc["case"]) {
            case_obj = doc["case"];
            emit([doc["#patient_id"], case_obj["case_id"]], case_obj);
        }
    }
}
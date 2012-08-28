function (doc, req) {
    //Filter function to just get device reports
    if (doc['doc_type'] == "XFormInstance" && doc['xmlns'] == "http://code.javarosa.org/devicereport") {
        return true;
    }
    else {
        return false;
    }
}
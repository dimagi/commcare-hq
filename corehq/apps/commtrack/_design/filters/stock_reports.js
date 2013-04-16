function(doc, req) {
    if (doc.doc_type == 'XFormInstance' && doc.form['@xmlns'] == 'http://openrosa.org/commtrack/stock_report') {
        return true;
    } else {
        return false;
    }
}

function(doc, req) {
    return ["trialconnect", "tc-test", "gc"].indexOf(doc.domain) > -1 && doc.doc_type === 'SMSLog'
}

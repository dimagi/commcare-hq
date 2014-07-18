function (doc) {
    // this is a direct port of the python case.xform.extract_case_blocks function
    var relevantDocTypes = [
        "XFormInstance", "XFormError", "XFormDuplicate",
        "XFormDeprecated", "SubmissionErrorLog", "XFormArchived"
    ];
    var deviceReportXmlns = "http://code.javarosa.org/devicereport";

    var shouldLook = function (doc) {
        return (relevantDocTypes.indexOf(doc.doc_type) !== -1 &&
            !(doc.xmlns === deviceReportXmlns ||
              doc['@xmlns'] === deviceReportXmlns)
        );

    };

    function typeOf(value) {
        // todo: this function now lives in 3 places in couch. any way to deduplicate?
        var s = typeof value;
        if (s === 'object') {
            if (value) {
                if (Object.prototype.toString.call(value) == '[object Array]') {
                    s = 'array';
                }
            } else {
                s = 'null';
            }
        }
        return s;
    }

    function isArray(obj) {
        return typeOf(obj) === "array";
    }

    function isObject(obj) {
        return typeOf(obj) === "object";
    }

    var emitCaseBlocksIn = function (subdoc) {

        var getCaseId = function (caseBlock) {
            return caseBlock['case_id'] || caseBlock['@case_id'] || null;
        };

        var emitIfId = function (caseBlock) {
            caseId = getCaseId(caseBlock);
            if (caseId) {
                emit([caseId, doc._id], null);
            }
        }

        var prop, i, caseId;

        if (isArray(subdoc)) {
            for (i = 0; i < subdoc.length; i++) {
                emitCaseBlocksIn(subdoc[i]);
            }
        } else if (isObject(subdoc)) {
            for (prop in subdoc) {
                if (subdoc.hasOwnProperty(prop)) {
                    if (prop === 'case') {
                        var caseOrCaseList = subdoc[prop];
                        if (isArray(caseOrCaseList)) {
                            for (i = 0; i < caseOrCaseList.length; i++) {
                                emitIfId(caseOrCaseList[i]);
                            }
                        } else {
                            emitIfId(caseOrCaseList);
                        }
                    }
                    else {
                        // recurse through sub properties
                        emitCaseBlocksIn(subdoc[prop]);
                    }
                }
            }
        }
    };
    if (shouldLook(doc)) {
        emitCaseBlocksIn(doc);
    }
}

function (doc) {
    if (doc.base_doc === 'IndicatorDocument') {
        var key = [doc.doc_type], i;
        for (i = 0; i < doc.group_by.length; i++) {
            key.push(doc[doc.group_by[i]]);
        }
        for (var calcName in doc) {
            if (doc.hasOwnProperty(calcName)) {
                // isObject(doc[calcName])
                if (Object.prototype.toString.call(doc[calcName]) === '[object Object]') {
                    for (var emitterName in doc[calcName]) {
                        if (doc[calcName].hasOwnProperty(emitterName)) {
                            for (i = 0; i < doc[calcName][emitterName].length; i++) {
                                var value = doc[calcName][emitterName][i];
                                emit(key.concat([calcName, emitterName, value[0]]), value[1]);
                            }
                        }
                    }
                }
            }
        }
    }
}
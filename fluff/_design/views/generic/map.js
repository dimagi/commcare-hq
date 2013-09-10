function (doc) {
    var excludes = ['group_by_type_map'];
    if (doc.base_doc === 'IndicatorDocument') {
        var key = [doc.doc_type], i;
        for (i = 0; i < doc.group_by.length; i++) {
            key.push(doc[doc.group_by[i]]);
        }
        for (var calcName in doc) {
            if (excludes.indexOf(calcName) === -1 && doc.hasOwnProperty(calcName)) {
                // isObject(doc[calcName])
                if (Object.prototype.toString.call(doc[calcName]) === '[object Object]') {
                    for (var emitterName in doc[calcName]) {
                        if (doc[calcName].hasOwnProperty(emitterName)) {
                            for (i = 0; i < doc[calcName][emitterName].length; i++) {
                                var value = doc[calcName][emitterName][i];
                                if (Object.prototype.toString.call(value) === '[object Object]') {
                                    var custom_key = value['group_by'] === null ? key : [doc.doc_type].concat(value['group_by']);
                                    emit(custom_key.concat([calcName, emitterName, value['date']]), value['value']);
                                } else {
                                    emit(key.concat([calcName, emitterName, value[0]]), value[1]);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

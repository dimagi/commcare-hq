/*global $, XMLSerializer */
var casexml = (function () {
    'use strict';
    var casexml = {
        iso: function (d) {
            function pad(n) {
                return n < 10 ? '0' + n : n;
            }
            return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate()) + 'T' + pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes()) + ':' + pad(d.getUTCSeconds()) + 'Z';
        },
        isonow: function () {
            return casexml.iso(new Date());
        },
        versions: {
            V2: '2.0'
        },
        versionToXMLNS: {
            '2.0': 'http://commcarehq.org/case/transaction/v2'
        },
        cloudcareEditXMLNS: "http://commcarehq.org/cloudcare/custom-edit",
        makeSerializableXML: function (jQueryObj) {
            jQueryObj.toString = function () {
                return new XMLSerializer.serializeToString(this[0]);
            };
            return jQueryObj;
        },
        CaseBlock: (function () {
            var CaseBlock = function (o) {
                var case_id = o.case_id,
                    date_modified = o.date_modified || casexml.isonow(),
                    user_id = o.user_id,
                    owner_id = o.owner_id,
                    case_type = o.case_type,
                    case_name = o.case_name,
                    create = o.create || false,
                    date_opened = o.date_opened,
                    update = o.update || {},
                    close = o.close || false,
                    index = o.index || {},
                    version = o.version || casexml.versions.V2,
                    compatibility_mode = o.compatability_mode || false,
                    keywords,
                    required,
                    requiredForCreate,
                    XMLNS,
                    create_or_update,
                    attrib,
                    $case,
                    $create,
                    $update,
                    $create_or_update,
                    $index,
                    $close,
                    key;

                keywords = {
                    case_type: true,
                    case_name: true,
                    owner_id: true,
                    date_opened: true
                };
                required = {
                    case_id: true,
                    user_id: true
                };
                requiredForCreate = {
                    case_type: true,
                    case_name: true
                };
                for (key in required) {
                    if (required.hasOwnProperty(key) && o[key] === undefined) {
                        throw {
                            type: 'missingArg',
                            arg: key
                        };
                    }
                }
                if (create) {
                    for (key in requiredForCreate) {
                        if (requiredForCreate.hasOwnProperty(key) && o[key] === undefined) {
                            throw {
                                type: 'missingArg',
                                arg: key
                            };
                        }
                    }
                }
                if (version !== casexml.versions.V2) {
                    throw {
                        type: 'invalidArg',
                        arg: 'version',
                        value: version
                    };
                }
                if (compatibility_mode !== false) {
                    throw {
                        type: 'invalidArg',
                        arg: 'compatibility_mode',
                        value: compatibility_mode
                    };
                }
                for (key in update) {
                    if (update.hasOwnProperty(key)) {
                        if (keywords.hasOwnProperty(key)) {
                            throw {
                                type: 'invalidUpdateProperty',
                                property: key
                            };
                        }
                    }
                }

                XMLNS = casexml.versionToXMLNS[version]; /* nodes that may appear in either the create or the update blocks */
                create_or_update = {
                    case_type: case_type,
                    case_name: case_name,
                    owner_id: owner_id
                };

                /* things that will end up as case block attributes */
                attrib = {
                    case_id: case_id,
                    date_modified: date_modified,
                    user_id: user_id,
                    xmlns: XMLNS
                };
                $case = $('<case/>').attr(attrib);
                $create = $('<create/>');
                $update = $('<update/>');
                $index = $('<index/>');
                $close = $('<close/>');
                $create_or_update = create ? $create : $update;

                if (date_opened !== undefined) {
                    $('<date_opened/>').text(date_opened).appendTo($update);
                }

                for (key in update) {
                    if (update.hasOwnProperty(key) && update[key] !== undefined) {
                        $('<' + key + '/>').text(update[key]).appendTo($update);
                    }
                }

                for (key in create_or_update) {
                    if (create_or_update.hasOwnProperty(key) && create_or_update[key] !== undefined) {
                        $('<' + key + '/>').text(create_or_update[key]).appendTo($create_or_update);
                    }
                }

                (function () {
                    var key, case_type, case_id;
                    for (key in index) {
                        if (index.hasOwnProperty(key)) {
                            case_type = index[key][0];
                            case_id = index[key][1];
                            if (case_id !== undefined) {
                                $('<' + key + '/>').attr({
                                    case_type: case_type
                                }).text(case_id).appendTo($index);
                            }
                        }
                    }
                }());

                if (create) {
                    $create.appendTo($case);
                }
                if ($update.is(':parent')) {
                    $update.appendTo($case);
                }
                if ($index.is(':parent')) {
                    $index.appendTo($case);
                }
                if (close) {
                    $close.appendTo($case);
                }
                casexml.makeSerializableXML($case);
                this.toXML = function () {
                    return $case;
                };
                this.asXFormInstance = function () {
                    return casexml.makeSerializableXML(
                        $('<data/>').attr({xmlns: casexml.cloudcareEditXMLNS}).append($case)
                    );
                };
            };
            CaseBlock.init = function (o) {
                return new CaseBlock(o);
            };
            return CaseBlock;
        }())
    };
    return casexml;
}());
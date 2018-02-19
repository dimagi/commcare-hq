/*global cheapxml, XMLSerializer */

var casexml = (function () {
    'use strict';
    var casexml = {
        guid: function (n) {
            var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                guid = [],
                i;
            n = n || 25;
            for (i = 0; i < n; i += 1) {
                guid.push(chars[Math.floor(Math.random() * chars.length)]);
            }
            return guid.join('');
        },
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
            V2: '2.0',
        },
        versionToXMLNS: {
            '2.0': 'http://commcarehq.org/case/transaction/v2',
        },
        cloudcareEditXMLNS: "http://commcarehq.org/cloudcare/custom-edit",
        makeSerializableXML: function (jQueryObj) {
            jQueryObj.serialize = function () {
                return new XMLSerializer().serializeToString(this[0]);
            };
            return jQueryObj;
        },
        openrosaXFormsXMLNS: 'http://openrosa.org/jr/xforms',
        Case: {
            wrap: function (o) {
                o.minus = function (that) {
                    var diff = {
                            properties: {},
                            indices: {},
                        },
                        property,
                        index;
                    if (this.case_id !== that.case_id) {
                        throw "Cannot subtract case with case_id '" + that.case_id +
                            "' from case with case_id '" + this.case_id + "'";
                    }
                    if (that.closed === true) {
                        throw "You cannot make changes to a closed case";
                    }
                    if (this.closed === true) {
                        diff.closed = this.closed;
                    }

                    diff.case_id = this.case_id;

                    for (property in this.properties) {
                        if (this.properties.hasOwnProperty(property)) {
                            if (this.properties[property] !== that.properties[property]) {
                                diff.properties[property] = this.properties[property];
                            }
                        }
                    }
                    for (property in that.properties) {
                        if (that.properties.hasOwnProperty(property)) {
                            if (!this.properties.hasOwnProperty(property)) {
                                diff.properties[property] = '';
                            }
                        }
                    }

                    for (index in this.indices) {
                        if (this.indices.hasOwnProperty(index)) {
                            if (this.indices[index].case_type !== (that.indices[index] || {}).case_type ||
                                    this.indices[index].case_id !== (that.indices[index] || {}).case_id) {
                                diff.indices[index] = this.indices[index];
                            }
                        }
                    }
                    for (index in that.indices) {
                        if (that.indices.hasOwnProperty(index)) {
                            if (!this.indices.hasOwnProperty(index)) {
                                diff.indices[index] = '';
                            }
                        }
                    }
                    if (this.date_modified !== that.date_modified) {
                        diff.date_modified = this.date_modified;
                    }
                    return casexml.CaseDelta.wrap(diff);
                };
                return o;
            },
        },
        CaseDelta: {
            wrap: function (o) {
                o.toXML = function (options) {
                    var $ = cheapxml.$,
                        user_id = options.user_id,
                        create = options.create || false,
                        version = options.version || casexml.versions.V2,
                        date_modified = options.date_modified || o.date_modified || casexml.isonow(),
                        case_id = o.case_id,
                        update = {},
                        closed = o.closed || false,
                        indices = o.index || {},
                        keywords = {
                            case_type: undefined,
                            case_name: undefined,
                            owner_id: undefined,
                            date_opened: undefined,
                        },
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
                    requiredForCreate = {
                        case_type: true,
                        case_name: true,
                    };
                    if (user_id === undefined) {
                        throw {
                            type: 'missingArg',
                            arg: 'user_id',
                        };
                    }
                    if (case_id === undefined) {
                        throw {
                            type: 'missingArg',
                            arg: 'case_id',
                        };
                    }
                    if (create) {
                        for (key in requiredForCreate) {
                            if (requiredForCreate.hasOwnProperty(key) && o.properties[key] === undefined) {
                                throw {
                                    type: 'missingArg',
                                    arg: key,
                                };
                            }
                        }
                    }

                    for (key in o.properties) {
                        if (o.properties.hasOwnProperty(key)) {
                            if (o.properties[key] === null) {
                                o.properties[key] = undefined;
                            }
                            if (keywords.hasOwnProperty(key)) {
                                keywords[key] = o.properties[key];
                            } else {
                                update[key] = o.properties[key];
                            }
                        }
                    }

                    XMLNS = casexml.versionToXMLNS[version]; /* nodes that may appear in either the create or the update blocks */
                    create_or_update = {
                        case_type: keywords.case_type,
                        case_name: keywords.case_name,
                        owner_id: keywords.owner_id,
                    };

                    /* things that will end up as case block attributes */
                    attrib = {
                        case_id: case_id,
                        date_modified: date_modified,
                        user_id: user_id,
                        xmlns: XMLNS,
                    };
                    $case = $('<case/>').attr(attrib);
                    $create = $('<create/>');
                    $update = $('<update/>');
                    $index = $('<index/>');
                    $close = $('<close/>');
                    $create_or_update = create ? $create : $update;

                    if (keywords.date_opened !== undefined) {
                        $('<date_opened/>').text(keywords.date_opened).appendTo($update);
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
                        for (key in indices) {
                            if (indices.hasOwnProperty(key)) {
                                case_type = indices[key][0];
                                case_id = indices[key][1];
                                if (case_id !== undefined) {
                                    $('<' + key + '/>').attr({
                                        case_type: case_type,
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
                    if (closed) {
                        $close.appendTo($case);
                    }
                    return $case;
                };
                o.asXFormInstance = function (options) {
                    var $ = cheapxml.$,
                        timeEnd = options.timeEnd || o.date_modified || casexml.isonow(),
                        timeStart = options.timeStart || '',
                        xform;
                    options.date_modified = timeEnd;
                    xform = $('<data/>').attr({xmlns: casexml.cloudcareEditXMLNS, name: options.form_name}).append(
                        $('<meta/>').attr({xmlns: casexml.openrosaXFormsXMLNS}).append(
                            $('<instanceID/>').text(casexml.guid()),
                            $('<timeStart/>').text(timeStart),
                            $('<timeEnd/>').text(timeEnd),
                            $('<userID/>').text(options.user_id),
                            $('<username/>').text(options.username)
                            //                            $('<deviceID/>')
                        )
                    ).append(o.toXML(options));
                    return xform;
                };
                return o;
            },
        },
    };
    return casexml;
}());

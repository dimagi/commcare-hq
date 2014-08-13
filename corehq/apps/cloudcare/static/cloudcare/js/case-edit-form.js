/*global eventize, uiElement, $, casexml, SaveButton, setTimeout, _ */
var CaseEditForm = (function () {
    'use strict';
    var CaseEditForm = function (o) {
        var that = this,
            edit = true,
            lang = o.lang,
            translate = function (label) {
                if (typeof label === 'object') {
                    return label[lang];
                } else {
                    return label;
                }
            },
            setWarning = function (spec, val) {
                alert(spec.label[lang] + ' has illegal value: ' + val);
                spec.element.ui.css('background-color', 'red');
            },
            propertyTypes = {
                'string': function (spec, callback) {
                    spec.stringToValue = spec.valueToString = function (str) {
                        return str || '';
                    };
                    spec.element = uiElement.input();
                    callback(spec);
                },
                'date': function (spec, callback) {
                    var dateFormat = 'd M. yy',
                        altFormat = 'yy-mm-dd';
                    spec.element = (function () {
                        var element = uiElement.input();
                        element.ui.find('input').datepicker({
                            dateFormat: dateFormat,
                            altFormat: altFormat
                        });
                        element.ui.css({
                            position: 'relative'
                        }).append(
                            $('<i/>').addClass('icon-calendar').css({
                                position: 'absolute',
                                right: 3,
                                top: 2
                            })
                        );
                        return element;
                    }());
                    spec.stringToValue = function (str) {
                        return $.datepicker.formatDate(altFormat, $.datepicker.parseDate(dateFormat, str));
                    };
                    spec.valueToString = function (val) {
                        try {
                            return $.datepicker.formatDate(dateFormat, $.datepicker.parseDate(altFormat, val || ''));
                        } catch (e) {
                            setWarning(spec, val);
                            return val;
                        }
                    };
                    callback(spec);
                },
                'select': function (spec, callback) {
                    var stringToValue = {},
                        valueToString = {},
                        choices = [],
                        i,
                        j;
                    for (i = 0; i < spec.choices.length; i += 1) {
                        if (spec.choices[i].stringValue === undefined) {
                            spec.choices[i].stringValue = spec.choices[i].value;
                        }
                        stringToValue[spec.choices[i].stringValue] = spec.choices[i].value;
                        // produce strictly, accept liberally
                        valueToString[spec.choices[i].value] = spec.choices[i].stringValue;
                        valueToString[spec.choices[i].stringValue] = spec.choices[i].stringValue;
                        if (spec.choices[i].accept) {
                            for (j = 0; j < spec.choices[i].accept.length; j += 1) {
                                valueToString[spec.choices[i].accept[j]] = spec.choices[i].stringValue;
                            }
                        }
                        choices.push({
                            label: translate(spec.choices[i].label),
                            value: spec.choices[i].stringValue
                        });
                    }
                    spec.element = uiElement.select(choices);
                    spec.stringToValue = function (str) {
                        return stringToValue[str];
                    };
                    spec.valueToString = function (val) {
                        var string;
                        if (val === undefined) {
                            string = '';
                        } else if (valueToString.hasOwnProperty(val)) {
                            string = valueToString[val];
                        } else {
                            setWarning(spec, val);
                            string = val;
                        }
                        return string;
                    };
                    callback(spec);
                },
                'group': function (spec, callback) {
                    $.ajax({
                        url: o.groupsUrl,
                        dataType: 'json',
                        success: function (data) {
                            var choices = [{
                                label: '(No one)',
                                value: '',
                                accept: [null]
                            }],
                                selectSpec = {
                                    label: spec.label,
                                    key: spec.key,
                                    type: 'select',
                                    choices: choices
                                },
                                i;
                            for (i = 0; i < data.length; i += 1) {
                                choices.push(data[i]);
                            }
                            propertyTypes.select(selectSpec, callback);
                        }
                    });
                }
            },
            timeStart,
            originalCase,
            keis = o.commcareCase,
            shouldCreate,
            caseSpec = o.caseSpec,
            availableProperties = caseSpec.propertySpecs,
            saveButton = SaveButton.init({
                save: function () {
                    var xform;
                    if (!keis.properties.case_type) {
                        keis.properties.case_type = caseSpec.case_type;
                    }
                    console.log(casexml.Case.wrap(keis).minus(originalCase));
                    xform = casexml.Case.wrap(keis).minus(originalCase).asXFormInstance({
                        timeStart: timeStart,
                        user_id: o.user_id,
                        create: shouldCreate
                    }).serialize();
                    console.log(xform);
                    saveButton.ajax({
                        url: o.receiverUrl,
                        type: 'post',
                        data: xform,
                        success: function (data) {
                            that.fire('restart');
                            if (shouldCreate) {
                                shouldCreate = false;
                                history.pushState({}, '', '../view/' + keis.case_id + '/?spec=' + caseSpec._id);
                            }
                            console.log(data);
                        }
                    });
                }
            }),
            home = o.home,
            fireChange = function () {
                saveButton.fire('change');
            },
            setControl = function (element, target, attr, strToValue) {
                element.on('change', fireChange);
                element.on('change', function () {
                    if (strToValue) {
                        target[attr] = strToValue(this.val());
                    } else {
                        target[attr] = this.val();
                    }
                    element.ui.attr('title', target[attr]);
                });
                that.on('edit:change', function () {
                    element.setEdit(edit);
                });
            },
            keyValueTable = function (o) {
                var mapping = o.mapping,
                    spec = o.spec,
                    $table = o.table || $('<table/>').addClass('key-value-table'),
                    i,
                    mkInput = function (value, spec, callback) {
                        propertyTypes[spec.type](spec, function (spec) {
                            var element = spec.element;
                            element.val(spec.valueToString(value));
                            element.ui.attr('title', value);
                            callback(element);
                        });
                    },
                    s,
                    $td,
                    $label,
                    setLoading = function ($td) {
                        setTimeout(function () {
                            if (!$td.is(':parent')) {
                                $td.text(translatedStrings.loading);
                            }
                        }, 200);
                    },
                    makeCallback = function (spec, mapping, $td, $label) {
                        return function (element) {
                            var forID;
                            setControl(element, mapping, spec.key, spec.stringToValue);
                            $td.html(element.ui);
                            forID = element.$edit_view.attr('id') || casexml.guid();
                            element.$edit_view.attr({id: forID});
                            $label.attr({'for': forID});
                        };
                    };
                for (i = 0; i < spec.length; i += 1) {
                    s = spec[i];
                    $td = $('<td/>');
                    $label = $('<label/>').text(translate(s.label));
                    $table.append(
                        $('<tr/>').append(
                            $('<th/>').append($label),
                            $td
                        )
                    );
                    setLoading($td);
                    mkInput(mapping[s.key], s, makeCallback(s, mapping, $td, $label));
                }
                return $table;
            },
            keisPropertiesSpec = _.chain(availableProperties).map(function (spec) {
                spec.label = spec.label || spec.key.replace(/[\-_]/g, ' ');
                return spec;
            }).value(),
            editLink,
            case_name_element = uiElement.input();

        eventize(that);

        if (keis) {
            shouldCreate = false;
        } else {
            shouldCreate = true;
            keis = {
                case_id: casexml.guid(),
                properties: {},
                indices: {}
            };
        }
        saveButton.ui.appendTo(home).attr({'id': 'case-edit-save-button'});
        editLink = $('<a href="#" id="case-edit-form-edit-link"/>').text('edit').click(function () {
            edit = !edit;
            that.fire('edit:change');
            return false;
        }).appendTo(home);
        $('<h1/>').appendTo(home).append(case_name_element.ui);

        that.on('restart', function () {
            originalCase = JSON.parse(JSON.stringify(keis));
            timeStart = o.timeStart || casexml.isonow();
            case_name_element.val(keis.properties.case_name || '');
        }).fire('restart');
        setControl(case_name_element, keis.properties, 'case_name');

        keyValueTable({
            mapping: keis.properties,
            spec: keisPropertiesSpec
        }).appendTo(home);
        //        keyValueTable({
        //            mapping: keis,
        //            spec: [{
        //                key: 'closed',
        //                label: {'en': 'Status'},
        //                type: 'select',
        //                choices: [{
        //                    label: {'en': 'Closed'},
        //                    stringValue: 'true',
        //                    value: true
        //                }, {
        //                    label: {'en': 'Open'},
        //                    stringValue: 'false',
        //                    value: false
        //                }]
        //            }]
        //        }).appendTo(home);
        saveButton.on('save', function () {
            edit = false;
            that.fire('edit:change');
        });
        that.on('edit:change', function () {
            if (edit) {
                editLink.hide();
            } else {
                editLink.show();
            }
        });
        that.fire('edit:change');
        /* make all the th's as wide as the widest */
        (function () {
            var max = 0;

            function getWidth(elem) {
                var $elem = $(elem),
                    div = $elem.clone().css({
                        position: 'absolute',
                        top: -1000,
                        fontSize: $elem.css('fontSize'),
                        fontFamily: $elem.css('fontFamily')
                    }).appendTo($('body')),
                    width = div.width();
                div.remove();
                return width;
            }

            function sameWidth(elems, padding) {
                elems.each(function () {
                    max = Math.max(getWidth(this), max);
                }).each(function () {
                    $(this).css({
                        width: max + (padding || 0)
                    });
                });
            }
            sameWidth(home.find('.key-value-table th'), 30);
            sameWidth(home.find('.key-value-table td'));
        }());
    };
    CaseEditForm.init = function (o) {
        return new CaseEditForm(o);
    };
    return CaseEditForm;
}());

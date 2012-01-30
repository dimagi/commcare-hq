/*global eventize */

var CaseEditForm = (function () {
    var setWarning = function (spec, val) {
            alert(spec.label + ' has illegal value: ' + val);
            spec.element.ui.css('background-color', 'red');
        },
        propertyTypes = {
            'date': function (spec) {
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
                        $('<div/>').addClass('ui-icon ui-icon-calendar').css({
                            position: 'absolute',
                            right: 3,
                            top: 2
                        })
                    );
                    return element;
                }());
                spec.stringToValue = function (str) {
                    return $.datepicker.formatDate(altFormat,
                        $.datepicker.parseDate(dateFormat, str)
                    );
                };
                spec.valueToString = function (val) {
                    try {
                        return $.datepicker.formatDate(dateFormat,
                            $.datepicker.parseDate(altFormat, val || '')
                        )
                    } catch (e) {
                        setWarning(spec, val);
                        return val;
                    }
                };
            },
            'select': function (spec) {
                var stringToValue = {},
                    valueToString = {},
                    i;
                console.log(spec);
                for (i = 0; i < spec.choices.length; i += 1) {
                    if (spec.choices[i].trueValue === undefined) {
                        spec.choices[i].trueValue = spec.choices[i].value;
                    }
                    stringToValue[spec.choices[i].value] = spec.choices[i].trueValue;
                    valueToString[spec.choices[i].trueValue] = spec.choices[i].value;
                }
                spec.element = uiElement.select(spec.choices);
                spec.stringToValue = function (str) {
                    return stringToValue[str];
                };
                spec.valueToString = function (val) {
                    if (valueToString.hasOwnProperty(val)) {
                        return valueToString[val];
                    } else {
                        setWarning(spec, val);
                        return val;
                    }
                };
            }
        },
        CaseEditForm = function (o) {
        var that = this,
            edit = true,
            timeStart,
            originalCase,
            keis = o.commcareCase,
            availableProperties = o.availableProperties || [],
            saveButton = SaveButton.init({
                save: function () {
                    var xform = casexml.Case.wrap(keis).minus(originalCase).asXFormInstance({
                        timeStart: timeStart,
                        user_id: o.user_id
                    }).serialize();

                    saveButton.ajax({
                        url: o.receiverUrl,
                        type: 'post',
                        data: xform,
                        success: function (data) {
                            that.fire('restart');
                            console.log(data);
                        }
                    });
                }
            }),
            home = o.home,
            keyValueTable = function (o) {
                var mapping = o.mapping,
                    spec = o.spec,
                    $table = o.table || $('<table/>').addClass('key-value-table'),
                    i,
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
                    mkInput = function (value, spec) {
                        var element;

                        if (propertyTypes.hasOwnProperty(spec.type)) {
                            propertyTypes[spec.type](spec);
                            element = spec.element;
                            element.val(spec.valueToString(value));
                        } else {
                            element = uiElement.input().val(value || '');
                        }
                        element.ui.attr('title', value);
                        return element;
                    },
                    element, s;
                for (i = 0; i < spec.length; i += 1) {
                    s = spec[i];
                    element = (s.format || mkInput)(mapping[s.key], s);
                    setControl(element, mapping, s.key, s.stringToValue);
                    $table.append(
                        $('<tr/>').append(
                            $('<th/>').text(s.label),
                            $('<td/>').append(element.ui)
                        )
                    );
                }
                return $table;
            },
            keisPropertiesSpec = _.chain(availableProperties).map(function (spec) {
                spec.label = spec.label || spec.key.replace(/[-_]/g, ' ');
                return spec;
            }).value(),
            editLink;

        eventize(that);
        that.on('restart', function () {
            originalCase = JSON.parse(JSON.stringify(keis));
            timeStart = o.timeStart || casexml.isonow();
        }).fire('restart');
        saveButton.ui.appendTo(home);
        $('<h1/>').text(keis.properties.case_name).appendTo(home);
        $('<h2/>').text('Properties').appendTo(home);
        editLink = $('<a href="#" id="case-edit-form-edit-link"/>').text('edit').click(function () {
            edit = !edit;
            that.fire('edit:change');
            return false;
        }).appendTo(home);
        keyValueTable({
            mapping: keis.properties,
            spec: keisPropertiesSpec
        }).appendTo(home);
        keyValueTable({
            mapping: keis,
            spec: [{
                key: 'closed',
                label: 'Status',
                type: 'select',
                choices: [{
                    label: 'Closed',
                    value: 'true',
                    trueValue: true
                }, {
                    label: 'Open',
                    value: 'false',
                    trueValue: false
                }]
            }]
        }).appendTo(home);

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
                    $(this).css({width: max + (padding || 0)});
                });
            }
            sameWidth(home.find('.key-value-table th'), 10);
            sameWidth(home.find('.key-value-table td'));
        }());
    };
    CaseEditForm.init = function (o) {
        return new CaseEditForm(o);
    };
    return CaseEditForm;
}());
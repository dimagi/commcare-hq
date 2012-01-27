/*global eventize */

var CaseEditForm = (function () {
    var CaseEditForm = function (o) {
        var that = this,
            edit = true,
            timeStart,
            originalCase,
            keis = o.commcareCase,
            availableProperties = o.availableProperties || [],
            saveButton = SaveButton.init({
                save: function () {
                    console.log(casexml.Case.wrap(keis).minus(originalCase).asXFormInstance({
                        timeStart: timeStart,
                        user_id: o.user_id
                    }).toString());
                    that.fire('restart');
                    saveButton.setState('saved');
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
                            console.log(target);
                        });
                        that.on('edit:change', function () {
                            element.setEdit(edit);
                        });
                    },
                    mkInput = function (x, s) {
                        var element = uiElement.input(),
                            dateFormat,
                            altFormat;

                        if (s.type === 'date') {
                            dateFormat = 'd M. yy';
                            altFormat = 'yy-mm-dd';
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
                            // TODO: I should really break this out better
                            // each type should come with a converter between the visible string value
                            // and the actual value that should be stored in the variable
                            // and that should be in a setting variable outside this function
                            s.strToValue = function (str) {
                                return $.datepicker.formatDate(altFormat,
                                    $.datepicker.parseDate(dateFormat, str)
                                );
                            };
                            element.val(
                                $.datepicker.formatDate(dateFormat,
                                    $.datepicker.parseDate(altFormat, x || '')
                                )
                            );
                        } else {
                            element.val(x || '');
                        }
                        return element;
                    },
                    element, s;
                for (i = 0; i < spec.length; i += 1) {
                    s = spec[i];
                    element = (s.format || mkInput)(mapping[s.key], s);
                    setControl(element, mapping, s.key, s.strToValue);
                    $table.append(
                        $('<tr/>').append(
                            $('<th/>').text(s.label),
                            $('<td/>').append(element.ui)
                        )
                    );
                }
                return $table;
            },
//            keisPropertiesSpec = _.sortBy(_.map(_.keys(keis.properties), function (property) {
//                return {
//                    key: property,
//                    label: property.replace(/[-_]/g, ' ')
//                };
//            }), function (entry) {
//                return entry.label;
//            })
            keisPropertiesSpec = _.chain(availableProperties).map(function (type, property) {
                return {
                    key: property,
                    label: property.replace(/[-_]/g, ' '),
                    type: type
                };
            }).value();

        eventize(that);
        that.on('restart', function () {
            originalCase = JSON.parse(JSON.stringify(keis));
            timeStart = o.timeStart || casexml.isonow();
        }).fire('restart');
        $('<h1/>').text(keis.properties.case_name).appendTo(home);
        $('<a href="#"/>').text('edit').click(function () {
            edit = !edit;
            that.fire('edit:change');
            return false;
        }).appendTo(home);
        saveButton.ui.appendTo(home);
        $('<h2/>').text('Properties').appendTo(home);
        keyValueTable({
            mapping: keis.properties,
            spec: keisPropertiesSpec
        }).appendTo(home);
        keyValueTable({
            mapping: keis,
            spec: [{
                key: 'closed',
                label: 'Status',
                format: function (x) {
                    return uiElement.select([{
                        label: 'Closed',
                        value: 'true'
                    }, {
                        label: 'Open',
                        value: 'false'
                    }]).val(x ? 'true' : 'false');
                },
                strToValue: function (str) {
                    return JSON.parse(str);
                }
            }]
        }).appendTo(home);

        saveButton.on('save', function () {
            edit = false;
            that.fire('edit:change');
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
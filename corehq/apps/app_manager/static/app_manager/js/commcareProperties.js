/*globals $, console, JSON, COMMCAREHQ, eventize */



var CommcareProperty = {
    wrap: function (json, initialValue, $home, settings, edit) {
        'use strict';
        var that = typeof json === 'object' ? json : JSON.parse(json),
            value,
            isEnabled = true,
            $input,
            disabledMessage,
            $disabledMessage,
            $tr = $("<tr />"),
            needsToBeSaved = false,
            parseCondition = function (condition) {
                var parts = condition ? condition.split('&&') : [],
                    parse_part = /\{([\$\w]+)\.([\w\-]+)\}='([\w\-]*)'/,
                    result,
                    type,
                    variable,
                    value,
                    i,
                    conditions = [];
                for (i = 0; i < parts.length; i += 1) {
                    result = parse_part.exec(parts[i]);
                    if (result === null) {
                        console.error("Unable to parse '" + parts[i] + "'");
                    } else {
                        type = result[1];
                        variable = result[2];
                        value = result[3];
                        try {
                            conditions.push({variable: settings[type][variable], value: value});
                        } catch (e) {
                            console.error("Error finding {" + type + "." + variable + "}");
                        }
                    }
                }
                return {
                    check: function () {
                        var i, c;
                        for (i = 0; i < conditions.length; i += 1) {
                            c = conditions[i];
                            if (c.variable.getImpliedValue() !== c.value) {
                                return false;
                            }
                        }
                        return true;
                    },
                    variables: conditions.map(function (p) { return p.variable; })
                };

            },

            getDefault = function () {
                var i;
                for (i = 0; i < that.contingent_default.length; i += 1) {
                    if (parseCondition(that.contingent_default[i].condition).check()) {
                        return that.contingent_default[i].value;
                    }
                }
                return that['default'];

            },
            setDisplay = function () {
                var displayValue;
                if (isEnabled) {
                    displayValue = value || that['default'];
                    if (edit) {
                        $input.removeAttr('disabled');
                        $disabledMessage.html('');
                    } else {
                        $tr.show();
                    }
                } else {
                    displayValue = getDefault();
                    if (edit) {
                        $input.attr('disabled', 'true');
                        $disabledMessage.html(disabledMessage);
                    } else {
                        $tr.hide();
                    }
                }

                if (edit) {
                    $input.val(displayValue);
                } else {
                    if (that.values === undefined) {
                        $input.text(displayValue);
                    } else {
                        $input.text(that.value_names[that.values.indexOf(displayValue)]);
                    }
                }
            },
            enabled = function (v, message) {
                if (v === undefined) {
                    return isEnabled;
                } else {
                    isEnabled = v;
                    disabledMessage = message;
                    setDisplay();
                }
            },
            initRequires = function () {
                var i,
                    requiresCondition = parseCondition(that.requires),
                    onChange,
                    onSave,
                    variables = [];
                onChange = function () {
                    var version = that.since || "1.1",
                        versionOK = COMMCAREHQ.app_manager.checkCommcareVersion(version),
                        is_enabled = true,
                        disabled_message;
                    if (!versionOK) {
                        is_enabled = false;
                        disabled_message = '<span class="ui-icon ui-icon-arrowthick-1-w"></span>Upgrade to CommCare ' + version + '!';
                    }
                    if (!requiresCondition.check()) {
                        is_enabled = false;
                    }
                    enabled(is_enabled, disabled_message);
                    that.fire('change');
                };
                onSave = function () {
                    that.save();
                };

                Array.prototype.push.apply(variables, requiresCondition.variables);
                for (i = 0; i < that.contingent_default.length; i++) {
                    var v = parseCondition(that.contingent_default[i].condition).variables;
                    Array.prototype.push.apply(variables, v);
                }
                for (i = 0; i < variables.length; i += 1) {
                    variables[i].on('change', onChange);
                    variables[i].on('save', onSave);
                }
                // bootstrap
                onChange();
                COMMCAREHQ.app_manager.on('change:commcareVersion', onChange);
            },
            render = function () {
                var $td = $('<td></td>'),
                    v,
                    v_name,
                    i;
                $('<th class="span3"></th>').text(that.name + " ").append(
                    COMMCAREHQ.makeHqHelp({
                        title: that.name,
                        content: that.description
                    })
                ).appendTo($tr);
                if (edit) {
                    if (that.values === undefined) {
                        $input = $("<input type='text' />");
                    } else {
                        $input = $("<select></select>");
                        for (i = 0; i < that.values.length; i += 1) {
                            v = that.values[i];
                            v_name = (that.value_names || that.values)[i];
                            $("<option></option>").attr('value', v).text((v === that['default'] ? "* " : " ") + v_name).appendTo($input);
                        }
                    }
                    $input.attr('name', that.id).change(function () {
                        that.val($(this).val());
                        that.save();
                    }).bind('textchange', function () {
                        that.fire('change');
                    }).appendTo($td);
                    // initialize value without saving to server

                } else {
                    $input = $("<span />").appendTo($td);
                }
                $disabledMessage = $('<span style="display: inline-block;"/>').appendTo($td).css({
                    width: '250px',
                    verticalAlign: 'top',
                    paddingLeft: '5px'
                });
                that.val(initialValue || null);
                initRequires();
                $td.appendTo($tr);
                if (that.disabled) {
                    if (that.val() === that['default']) {
                        $tr.hide();
                    } else {
                        $tr.css({border: '1px solid red'});
                        // This is an abstraction violation
                        $disabledMessage.text("Oops! This setting shouldn't be here. Could you change it to the default to make it go away? Sorry about that.");
                    }
                }
                return $home.append($tr);
            },
            getImpliedValue = function () {
                /* differs from val in that it returns the implied value
                    even if the widget is not enabled (instead of null)
                 */
                return value || getDefault();
            },
            val = function (v) {
                var theDefault = that['default'];
                if (v === undefined) {
                    if (enabled()) {
                        return value || theDefault;
                    } else {
                        return null;
                    }
                } else if (value !== v) {
                    // if this is the first time value is being set
                    // then it doesn't need to be saved
                    needsToBeSaved = (value !== undefined);
                    value = (v === theDefault ? null : v);
                    setDisplay();
                    that.fire('change');
                }
            },
            save = function () {
                if (needsToBeSaved) {
                    that.fire('save');
                }
            };
        eventize(that);
        that.contingent_default = that.contingent_default || [];
        that.render = render;
        that.val = val;
        that.getImpliedValue = getImpliedValue;
        that.enabled = enabled;
        that.save = save;
        return that;
    }
};
var CommcareSettings = {
    wrap: function (json, initialValues, $home, saveURL, edit, saveButtonHolder) {
        'use strict';
        var that = typeof json === 'object' ? json : JSON.parse(json),
            getHome = function (p) {
                if (typeof $home === "function") {
                    return $home(p);
                } else {
                    return $home;
                }
            },
            $homes,
            test_serialize = function () {
                var expected = {},
                    output = that.serialize(),
                    check = function (dict) {
                        var key;
                        for (key in dict) {
                            if (dict.hasOwnProperty(key)) {
                                if (dict[key] !== expected[key]) {
                                    console.error(key + ' set to ' + dict[key] + '! (Expected ' + expected[key] + ')');
                                }
                            }
                        }
                    };
                $homes.find('[name]').each(function () {
                    expected[$(this).attr('name')] = $(this).attr('disabled') ? null : $(this).val();
                });
                check(output.features);
                check(output.properties);
            },
            render = function () {
                var i, p, $pHome,
                    onChange = function () {
                        test_serialize();
                        that.saveButton.fire('change');
                    };
                $homes = $();
                that.properties = {};
                that.features = {};
                that.$parent = {'case_sharing': (function () {
                    var el = $('#case-sharing-select'),
                        that = {
                            val: function () {
                                return el.val()
                            },
                            getImpliedValue: function () {
                                return that.val();
                            }
                        };
                    eventize(that);
                    el.change(function () {
                        that.fire('change');
                    });
                    return that;
                }())};

                for (i = 0; i < that.length; i += 1) {
                    p = that[i];
                    p.type = p.type || "properties";
                    $pHome = getHome(p);
                    $.merge($homes, $pHome);
                    CommcareProperty.wrap(p, (initialValues[p.type] || {})[p.id], $pHome, that, edit);
                    // make properties/features available as e.g. that.properties.logenabled
                    that[p.type][p.id] = p;
                }


                for (i = 0; i < that.length; i += 1) {
                    that[i].render();
                    that[i].on('change', onChange);
                }
                return $.unique($homes);
            },
            serialize = function () {
                var s = {features: {}, properties: {}}, p, i;
                for (i = 0; i < that.length; i += 1) {
                    p = that[i];
                    s[p.type][p.id] = p.val();
                }
                return s;
            },
            save = function () {
                that.saveButton.ajax({
                    url: saveURL,
                    type: "POST",
                    data: {profile: JSON.stringify(serialize())},
                    dataType: "json",
                    success: function (data) {
                        COMMCAREHQ.app_manager.updateDOM(data.update);
                    }
                });
            };
        that.saveButton = COMMCAREHQ.SaveButton.init({
            save: save,
            unsavedMessage: "You have unsaved CommCare Settings."
        });
        if (edit) {
            that.saveButton.ui.appendTo(saveButtonHolder);
        }

        eventize(that);
        that.render = render;
        that.serialize = serialize;

        return that;
    }
};

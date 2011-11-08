/*globals $, console, JSON */

var eventize = function (that) {
    var events = {};
    that.on = function (tag, callback) {
        if (events[tag] === undefined) {
            events[tag] = [];
        }
        events[tag].push(callback);
        return that;
    };
    that.fire = function (tag, e) {
        var i;
        if (events[tag] !== undefined) {
            for (i = 0; i < events[tag].length; i += 1) {
                events[tag][i].apply(that, [e]);
            }
        }
        return that;
    };
};

var CommcareProperty = {
    wrap: function (json, initialValue, $home, settings, saveURL, edit) {
        var that = typeof json === 'object' ? json : JSON.parse(json),
            value,
            isEnabled,
            $input,
            $tr = $("<tr />"),
            needsToBeSaved = false,
            initialValue = initialValue || null,
            parseCondition = function (condition) {
                var parts = condition ? condition.split('&&') : [],
                    parse_part = /\{(\w+)\.([\w_\-]+)\}='(.*)'/,
                    result,
                    type, variable, value,
                    i,
                    repr = [];
                for (i = 0; i < parts.length; i += 1) {
                    result = parse_part.exec(parts[i]);
                    if (result === null) {
                        console.log("Unable to parse '" + things[i] + "'");
                    } else {
                        type = result[1];
                        variable = result[2];
                        value = result[3];
                        try {
                            repr.push({variable: settings[type][variable], value:value});
                        } catch(e) {
                            console.log("Error finding {" + type + "." + variable + "}");
                        }
                    }
                }
                return {
                    check: function () {
                        var i;
                        for (i = 0; i < repr.length; i += 1) {
                            if(repr[i].variable.val() !== repr[i].value) {
                                return false;
                            }
                        }
                        return true;
                    },
                    variables: repr.map(function(p){return p.variable;})
                };

            },
            enabled = function (v) {
                if (v === undefined) {
                    return isEnabled;
                } else {
                    isEnabled = v;
                    if (isEnabled) {
                        if (edit) {
                            $input.removeAttr('disabled');
                        } else {
                            $tr.show();
                        }
                    } else {
                        if (edit) {
                            $input.attr('disabled', 'true');
                        } else {
                            $tr.hide();
                        }
                    }
                }
            },
            initRequires = function () {
                var i,
                    requiresCondition = parseCondition(that.requires),
                    onChange, onSave;
                onChange = function () {
                    enabled(requiresCondition.check());
                };
                onSave = function () {
                    if (requiresCondition.check()) {
                        that.save();
                    } else {
                        val(null);
                        that.save();
                    }
                };
                for (i = 0; i < requiresCondition.variables.length; i += 1) {
                    requiresCondition.variables[i].on('change', onChange);
                    requiresCondition.variables[i].on('save', onSave);
                }
                // bootstrap
                onChange();
            },
            render = function () {
                var $td = $("<td />"),
                    v, v_name,
                    i;
                $("<th></th>").text(that.name + " ").append(
                    $("<span></span>").addClass('help-link').attr('data-help-key', that.id)
                ).append(
                    $("<div />").addClass('help-text').attr('data-help-key', that.id).text(that.description)
                ).appendTo($tr);
                if (edit) {
                    if (that.values === undefined) {
                        $input = $("<input type='text' />");
                    } else {
                        $input = $("<select></select>");
                        for (i = 0; i < that.values.length; i += 1) {
                            v = that.values[i];
                            v_name = (that.value_names || that.values)[i];
                            $("<option></option>").attr('value', v).text((v===that["default"] ? "* " : " ") + v_name).appendTo($input);
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
                that.val(initialValue);
                initRequires();
                $td.appendTo($tr);
                return $home.append($tr);
            },
            val = function (v) {
                var v_or_default;
                if (v === undefined) {
                    return value || that['default'];
                } else if (value !== v) {
                    v_or_default = v || that['default'];
                    // if this is the first time value is being set
                    // then it doesn't need to be saved
                    needsToBeSaved = (value !== undefined);
                    value = (v === that['default'] ? null : v);
                    if (edit) {
                        $input.val(v_or_default);
                    } else {
                        if (that.values === undefined) {
                            $input.text(v_or_default);
                        } else {
                            $input.text(that.value_names[that.values.indexOf(v_or_default)]);
                        }
                    }
                    that.fire('change');
                }
            },
            save = function () {
                if (needsToBeSaved) {
                    that.fire('save');
                }
            };
        eventize(that);
//        that.on('save', function(){
//            var $msg = $('<span />').text("saving...").appendTo($input.parent()),
//                data = {};
//            data[that.type] = {};
//            data[that.type][that.id] = that.val();
//            $.ajax({
//                url: saveURL,
//                type: "POST",
//                dataType: "json",
//                data: {profile: JSON.stringify(data)},
//                success: function (data) {
//                    needsToBeSaved = false;
//                    $msg.text('saved!').fadeOut('slow', function(){
//                        $msg.remove();
//                    });
//                },
//                error: function (jqHXR) {
//                    $msg.text('Error! Please reload page');
//                }
//            });
//        });
        that.render = render;
        that.val = val;
        that.enabled = enabled;
        that.save = save;
        return that;
    }
};
var CommcareSettings = {
    wrap: function (json, initialValues, $home, saveURL, edit, saveButtonHolder) {
        var that = typeof json === 'object' ? json : JSON.parse(json),
            getHome = function(p){
                if (typeof $home === "function") {
                    return $home(p);
                } else {
                    return $home;
                }
            },
            render = function () {
                var i, p, $homes = $(), $pHome;
                that.properties = {};
                that.features = {};

                for (i = 0; i < that.length; i += 1) {
                    p = that[i];
                    p.type = p.type || "properties";
                    $pHome = getHome(p);
                    $.merge($homes, $pHome);
                    CommcareProperty.wrap(p, (initialValues[p.type] || {})[p.id], $pHome, that, saveURL, edit);
                    // make properties/features available as e.g. that.properties.logenabled
                    that[p.type][p.id] = p;
                }
                
                for (i = 0; i < that.length; i += 1) {
                    that[i].render();
                    that[i].on('change', function(){
                        that.saveButton.fire('change');
                    });
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
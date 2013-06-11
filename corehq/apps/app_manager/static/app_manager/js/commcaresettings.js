function CommcareSettings(options) {
    var self = this;
    var initialValues = options.values;
    self.sections = options.sections;
    self.edit = ko.observable(options.edit);

    self.settings = [];
    self.settingsIndex = {};
    (function () {
        for (var i = 0; i < self.sections.length; i++) {
            var section = self.sections[i];
            for (var j = 0; j < section.settings.length; j++) {
                var setting = section.settings[j];

                self.settings.push(setting);

                if (!self.settingsIndex[setting.type]) {
                    self.settingsIndex[setting.type] = {};
                }
                self.settingsIndex[setting.type][setting.id] = setting;
            }
        }
    }());
    self.settingsIndex.$parent = {
        doc_type: {
            visibleValue: function () {
                return initialValues.$parent.doc_type;
            }
        }
    };

    self.parseCondition = function (condition) {
        var parts = condition ? condition.split('&&') : [],
            parse_part = /\{([\$\w]+)\.([\w\-]+)\}=('([\w\-]*)'|(true)|(false))/,
            result,
            type,
            setting,
            value,
            i,
            conditions = [];
        for (i = 0; i < parts.length; i += 1) {
            result = parse_part.exec(parts[i]);
            if (result === null) {
                console.error("Unable to parse '" + parts[i] + "'");
            } else {
                type = result[1];
                setting = result[2];
                value = result[3];
                if ("'" === value[0]) {
                    value = result[4];
                } else {
                    value = JSON.parse(value);
                }
                try {
                    conditions.push({setting: self.settingsIndex[type][setting], value: value});
                } catch (e) {
                    console.error("Error finding {" + type + "." + setting + "}");
                }
            }
        }
        return {
            check: function () {
                var i, c;
                for (i = 0; i < conditions.length; i += 1) {
                    c = conditions[i];
                    if (c.setting.visibleValue() !== c.value) {
                        return false;
                    }
                }
                return true;
            },
            settings: conditions.map(function (p) { return p.setting; })
        };

    };

    _(self.settings).each(function (setting) {
        var value = initialValues[setting.type][setting.id];
        setting.contingent_default = setting.contingent_default || [];
        setting.since = setting.since || '1.1';

        setting.value = ko.observable(value);
        setting.valueIsLegal = function () {
            // to be overridden
            return true;
        };
        
        setting.inputId = setting.id + '-input';


        setting.parsedCondition = ko.computed(function () {
            return self.parseCondition(setting.requires);
        });
        setting.versionOK = ko.computed(function () {
            return COMMCAREHQ.app_manager.checkCommcareVersion(setting.since);
        });
        setting.enabled = ko.computed(function () {
            var condition = setting.parsedCondition();
            return setting.versionOK() && condition.check();
        });
        setting.disabledMessage = ko.computed(function () {
            if (!setting.enabled()) {
                var versionOK = setting.versionOK();
                if (!versionOK) {
                    return 'Upgrade to CommCare ' + setting.since + '!';
                } else {
                    var condition = setting.parsedCondition();
                    var names = _(condition.settings).map(function (setting) {
                        return setting.name;
                    });
                    return 'Auto-set by ' + names.join(', ')
                }
            } else {
                return '';

            }
        });
        setting.computeDefault = ko.computed(function () {
            var i, condition, _case;
            for (i = 0; i < setting.contingent_default.length; i += 1) {
                _case = setting.contingent_default[i];
                condition = self.parseCondition(_case.condition);
                if (condition.check()) {
                    return _case.value;
                }
            }
            return setting['default'];
        });
        setting.visibleValue = ko.computed({
            read: function () {
                var retu;
                if (setting.enabled()) {
                    retu = setting.value() || setting.computeDefault();
                } else {
                    retu = setting.computeDefault();
                }
                return retu;
            },
            write: function (value) {
                setting.value(value);
            }
        });
        setting.visible = ko.computed(function () {
            return !(
                (setting.disabled && setting.visibleValue() === setting['default']) ||
                    (setting.hide_if_not_enabled && !setting.enabled())
                );
        });
        setting.disabledButHasValue = ko.computed(function () {
            return setting.disabled && setting.visibleValue() !== setting['default'];
        });

        // valueToSave is only ever used during serialization/save;
        // different from visibleValue
        // in that you want to save null and not the shown value
        // if the setting is disabled
        setting.valueToSave = ko.computed({
            read: function () {
                if (setting.enabled()) {
                    return setting.value() || setting.computeDefault();
                } else {
                    return null;
                }
            }
        });
        var wrap = CommcareSettings.widgets[setting.widget];
        if (wrap) {
            wrap(setting);
        }
        setting.hasError = ko.computed(function () {
            return setting.disabledButHasValue() || !setting.valueIsLegal();
        });
    });

    _(self.sections).each(function (section) {
        section.notEmpty = ko.computed(function () {
            return _(section.settings).some(function (setting) {
                return setting.visible();
            });
        });
        section.reallyCollapse = ko.computed(function () {
            section.collapse || _(section.settings).some(function (setting) {
                return setting.hasError();
            });
        });
    });

    self.serialize = ko.computed(function () {
        var blob = {};
        _(self.settings).each(function (setting) {
            if (!blob[setting.type]) {
                blob[setting.type] = {};
            }
            if (setting.valueToSave() !== null) {
                blob[setting.type][setting.id] = setting.valueToSave();
            }
        });
        return blob;
    });

    self.state = ko.observable('saved');
    setTimeout(function () {
        self.serialize.subscribe(function () {
            self.state('save');
        });
    }, 0);
    self.saveOptions = ko.computed(function () {
        return {
            url: options.urls.save,
            data: JSON.stringify(self.serialize()),
            type: 'post',
            dataType: 'json',
            success: function (data) {
                COMMCAREHQ.app_manager.updateDOM(data.update);
            }
        };
    });

}
CommcareSettings.widgets = {};

CommcareSettings.widgets.select = function (self) {
    var values = ko.utils.unwrapObservable(self.values);
    var value_names = ko.utils.unwrapObservable(self.value_names);
    if (!values || !value_names || values.length !== value_names.length) {
        console.error("Widget select requires values " +
            "and value_names of equal length", self);
        throw {};
    }
    self.options = ko.computed(function () {
        var options = [];
        for (var i = 0; i < values.length; i++) {
            options.push({
                label: (self['default'] === values[i] ? '* ' : '') +
                    value_names[i],
                value: values[i]
            });
        }
        return options;
    });
    self.selectOption = function (selectedOption) {
        if (selectedOption) {
            self.visibleValue(selectedOption.value);
        }
    };
    self.selectedOption = ko.computed({
        read: function () {
            var visibleValue = self.visibleValue(),
                retu;
            for (var i = 0; i < self.options().length; i++) {
                if (self.options()[i].value === visibleValue) {
                    retu = self.options()[i];
                    if (!retu) {
                        console.error(self.type + '.' + self.id, retu);
                        throw {};
                    }
                    return retu;
                }
            }
            return null;
        },
        write: self.selectOption
    });
    self.writeSelectedOption = ko.computed({
        read: function () { return null; },
        write: self.selectOption
    });
    self.valueIsLegal = function () {
        var value = self.value();
        return !value || _(self.options()).some(function (option) {
            return option.value === value;
        });
    };
};

CommcareSettings.widgets.bool = function (self) {
    if (!self.values) {
        self.values = [true, false];
    }
    self.boolValue = ko.computed({
        read: function () {
            return !!(self.visibleValue() === self.values[0]);
        },
        write: function (value) {
            self.visibleValue(
                value ? self.values[0] : self.values[1]
            );
        }
    });
};

CommcareSettings.widgets.build_spec = function (self) {
    CommcareSettings.widgets.select(self);
    self.widget_template = 'CommcareSettings.widgets.select';
    self.visibleValue.subscribe(function () {
        var majorVersion = self.visibleValue().split('/')[0].split('.').slice(0,2).join('.');
        COMMCAREHQ.app_manager.setCommcareVersion(majorVersion);
    });
};

$(function () {
    ko.bindingHandlers.passwordSetter = {
        init: function (element, valueAccessor) {
            var observableValue = valueAccessor();
            $(element).password_setter({title: ''});
            $(element).on('textchange change', function () {
                observableValue($(element).val());
            });
        }
    }
});
"use strict";
hqDefine('app_manager/js/forms/advanced/case_properties', function () {
    var caseConfigUtils = hqImport('app_manager/js/case_config_utils');

    var casePropertyBase = {
        mapping: {
            include: ['key', 'path', 'required'],
        },
        wrap: function (data, action) {
            var self = ko.mapping.fromJS(data, caseProperty.mapping);
            self.action = action;
            self.isBlank = ko.computed(function () {
                return !self.key() && !self.path();
            });
            self.caseType = ko.computed(function () {
                return self.action.case_type();
            });
            self.updatedDescription = ko.observable('');
            self.description = ko.computed({
                read: function () {
                    if (self.updatedDescription()) {
                        return self.updatedDescription();
                    }
                    var config = self.action.caseConfig;
                    var type = config.descriptionDict[self.caseType()];
                    if (type) {
                        return type[self.key()] || '';
                    }
                },
                write: function (value) {
                    self.updatedDescription(value);
                },
            });
            return self;
        },
    };

    var caseProperty = {
        mapping: casePropertyBase.mapping,
        wrap: function (data, action) {
            var self = casePropertyBase.wrap(data, action);

            // for compatibility with common templates
            self.case_transaction = {
                // template: case-config:case-properties:question
                allow: {
                    repeats: function () {
                        return action.allow.repeats();
                    },
                },
                // template: case-config:case-transaction:case-properties
                suggestedSaveProperties: ko.computed(function () {
                    return caseConfigUtils.filteredSuggestedProperties(
                        self.action.suggestedProperties(),
                        self.action.case_properties()
                    );
                }),
            };

            self.defaultKey = ko.computed(function () {
                var path = self.path() || '';
                var value = path.split('/');
                value = value[value.length - 1];
                return value;
            });
            self.repeat_context = function () {
                return action.caseConfig.get_repeat_context(self.path());
            };
            self.validate = ko.computed(function () {
                if (self.path() || self.key()) {
                    if (action.propertyCounts()[self.key()] > 1) {
                        return gettext("Property updated by two questions");
                    } else if (action.caseConfig.reserved_words.indexOf(self.key()) !== -1) {
                        return gettext("Reserved word: ") + '<strong>' + self.key() + '</strong>';
                    } else if (self.repeat_context() && self.repeat_context() !== self.action.repeat_context()) {
                        return gettext('Inside the wrong repeat!');
                    } else if (action.subcase() && _(self.key()).contains('/')) {
                        return gettext('Parent property references not allowed for subcases');
                    }
                }
                return null;
            });

            return self;
        },
    };

    var casePreloadProperty = {
        wrap: function (data, action) {
            var self = casePropertyBase.wrap(data, action);

            // for compatibility with common templates
            self.case_transaction = {
                // template: case-config:case-properties:question
                allow: {
                    repeats: function () {
                        return action.allow.repeats();
                    },
                },
                // template: case-config:case-transaction:case-preload
                suggestedPreloadProperties: ko.computed(function () {
                    return caseConfigUtils.filteredSuggestedProperties(
                        self.action.suggestedProperties(),
                        self.action.preload()
                    );
                }),
            };
            self.defaultKey = ko.computed(function () {
                return '';
            });
            self.validateProperty = ko.computed(function () {
                if (self.path() || self.key()) {
                    if (action.caseConfig.reserved_words.indexOf(self.key()) !== -1) {
                        return gettext("Reserved word: ") + '<strong>' + self.key() + '</strong>';
                    } else if (action.subcase() && _(self.key()).contains('/')) {
                        return gettext('Parent property references not allowed for subcases');
                    }
                }
                return null;
            });
            self.validateQuestion = ko.computed(function () {
                if (self.path()) {
                    if (action.preloadCounts()[self.path()] > 1) {
                        return gettext("Two properties load to the same question");
                    }
                }
                return null;
            });

            return self;
        },
    };

    return {
        caseProperty: caseProperty,
        casePreloadProperty: casePreloadProperty,
    };
});

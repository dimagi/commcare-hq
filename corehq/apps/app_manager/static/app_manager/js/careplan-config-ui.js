
var CareplanConfig = (function () {
    'use strict';
    var PropertyBase = {
        mapping: {
            include: ['key', 'path']
        },
        wrap: function (data, transaction) {
            var self = ko.mapping.fromJS(data, PropertyBase.mapping);
            self.case_transaction = transaction;

            self.isBlank = ko.computed(function () {
                return !self.key() && !self.path();
            });

            // for compatibility with templates
            self.required = function () {
                return false;
            };

            return self;
        }
    };

    var Question = {
        wrap: function (data, transaction) {
            var self = PropertyBase.wrap(data, transaction);

            self.validateQuestion = ko.computed(function () {
                if (self.path()) {
                    if (transaction.propertyPathCounts()[self.path()] > 1) {
                        return "Question is being used twice.";
                    }
                    if (transaction.preloadCounts()[self.path()] > 1) {
                        return "Two properties load to the same question";
                    }
                }
                return null;
            });
            self.validateProperty = ko.computed(function () {
                if (self.path() || self.key()) {
                    if (transaction.propertyKeyCounts()[self.key()] > 1) {
                        return "Property updated by two questions";
                    }
                }
                return null;
            });

            self.validate = ko.computed(function () {
                return self.validateProperty() || self.validateQuestion();
            });
            return self;
        }
    };

    var CaseProperty = {
        wrap: function (data, transaction) {
            var self = PropertyBase.wrap(data, transaction);

            self.defaultKey = ko.computed(function () {
                var path = self.path() || '';
                var value = path.split('/');
                value = value[value.length - 1];
                return value;
            });
            self.repeat_context = function () {
                return transaction.careplanConfig.get_repeat_context(self.path());
            };
            self.validateQuestion = ko.computed(function () {
                if (self.path()) {
                    if (transaction.propertyPathCounts()[self.path()] > 1) {
                        return "Question is being used twice.";
                    }
                }
            });
            self.validateProperty = ko.computed(function () {
                if (self.path() || self.key()) {
                    if (transaction.propertyKeyCounts()[self.key()] > 1) {
                        return "Property updated by two questions";
                    }
                    if (transaction.careplanConfig.reserved_words.indexOf(self.key()) !== -1) {
                        return '<strong>' + self.key() + '</strong> is a reserved word';
                    }
                    if (self.repeat_context() && self.repeat_context() !== transaction.repeat_context()) {
                        return 'Inside the wrong repeat!';
                    }
                    if (self.key().indexOf('/') !== -1) {
                        return 'Updating properties in the parent case is not supported';
                    }
                }

                return null;
            });

            self.validate = ko.computed(function () {
                return self.validateProperty() || self.validateQuestion();
            });

            return self;
        }
    };

    var CasePreload = {
        wrap: function (data, transaction) {
            var self = PropertyBase.wrap(data, transaction);
            self.defaultKey = ko.computed(function () {
                var path = self.path() || '';
                var value = path.split('/');
                value = value[value.length - 1];
                return value;
            });

            self.validateQuestion = ko.computed(function () {
                if (self.path()) {
                    if (transaction.preloadCounts()[self.path()] > 1) {
                        return "Two properties load to the same question";
                    }
                }
                return null;
            });
            self.validateProperty = ko.computed(function () {
                if (self.key()) {
                    if (transaction.careplanConfig.reserved_words.indexOf(self.key()) !== -1) {
                        return '<strong>' + self.key() + '</strong> is a reserved word';
                    }
                    if (transaction.careplanConfig.mode === 'create' &&
                            self.key().indexOf('/') === -1) {
                        return 'Only parent properties can be loaded here.';
                    }
                }
                return null;
            });

            self.validate = ko.computed(function () {
                return self.validateProperty() || self.validateQuestion();
            });
            return self;
        }
    };

    var CareplanTransaction = {
        mapping: function (self) {
            return {
                include: [
                    'fixedQuestions',
                    'case_properties',
                    'case_preload'
                ],
                fixedQuestions: {
                    create: function (options) {
                        return Question.wrap(options.data, self);
                    }
                },
                case_properties: {
                    create: function (options) {
                        return CaseProperty.wrap(options.data, self);
                    }
                },
                case_preload: {
                    create: function (options) {
                        return CasePreload.wrap(options.data, self);
                    }
                }
            };
        },
        wrap: function (data, careplanConfig) {
            var self = {};
            ko.mapping.fromJS(data, CareplanTransaction.mapping(self), self);
            self.careplanConfig = careplanConfig;

            // link self.case_name to corresponding path observable
            // in case_properties for convenience
            try {
                self.case_name = _(self.fixedQuestions()).find(function (p) {
                    return p.name() === 'name_path';
                }).path;
            } catch (e) {
                self.case_name = null;
            }

            var count = function (itemLists, accessor) {
                var _count = {};
                var update_count = function (p) {
                    var key = p[accessor]();
                    if (!_count.hasOwnProperty(key)) {
                        _count[key] = 0;
                    }
                    _count[key] += 1;
                }
                _(itemLists).each(function (list) {
                    _(list()).each(function (p) {
                        update_count(p);
                    });
                });
                return _count;
            };

            self.suggestedProperties = ko.computed(function () {
                var properties = {
                    all: [],
                    preload: [],
                    save: []
                };
                var propertiesMap = self.careplanConfig.propertiesMap;
                var caseType = self.careplanConfig.caseType;
                if (_(propertiesMap).has(caseType)) {
                    properties.all = propertiesMap[caseType]();
                    if (self.careplanConfig.mode === 'create') {
                        properties.preload = _.filter(properties.all, function (p) {
                            return p.indexOf('/') != -1;
                        });
                    } else {
                        properties.preload = properties.all;
                    }
                    properties.save = _.filter(properties.all, function (p) {
                        return p.indexOf('/') === -1;
                    });
                }
                properties.save = CC_UTILS.filteredSuggestedProperties(
                    properties.save,
                    self.case_properties()
                );
                properties.preload = CC_UTILS.filteredSuggestedProperties(
                    properties.preload,
                    self.case_preload()
                );
                return properties;
            });

            self.suggestedPreloadProperties = ko.computed(function () {
                return self.suggestedProperties().preload;
            });

            self.suggestedSaveProperties = ko.computed(function () {
                return self.suggestedProperties().save;
            });

            var updates = [self.fixedQuestions, self.case_properties];
            self.propertyPathCounts = ko.computed(function () {
                return count(updates, 'path');
            });

            self.propertyKeyCounts = ko.computed(function () {
                return count(updates, 'key');
            });

            self.preloadCounts = ko.computed(function () {
                return count([self.fixedQuestions, self.case_preload], 'path');
            });

            self.addProperty = function () {
                var property = CaseProperty.wrap({
                    path: '',
                    key: ''
                }, self);

                self.case_properties.push(property);
            };

            self.removeProperty = function (property) {
                self.case_properties.remove(property);
            };

            self.addPreload = function () {
                var property = CasePreload.wrap({
                    path: '',
                    key: ''
                }, self);

                self.case_preload.push(property);
            };

            self.removePreload = function (property) {
                self.case_preload.remove(property);
            };

            self.repeat_context = function () {
                return self.careplanConfig.get_repeat_context(self.case_name());
            };

            self.ensureBlankProperties = function () {
                var items = [{
                    properties: self.case_properties(),
                    addProperty: self.addProperty
                }];
                if (self.case_preload) {
                    items.push({
                        properties: self.case_preload(),
                        addProperty: self.addPreload
                    });
                }
                _(items).each(function (item) {
                    var properties = item.properties;
                    var last = properties[properties.length-1];
                    if (last && !last.isBlank()) {
                        item.addProperty();
                    }
                });
            };

            // for compatibility with templates
            self.allow = {
                repeats: function () {
                    return true;
                }
            };

            self.unwrap = function () {
                CareplanTransaction.unwrap(self);
            };

            return self;
        },
        unwrap: function (self) {
            var unwrap = function (list, filter) {
                if (filter) {
                    list = _.filter(list, function (p) {
                        return !p.isBlank();
                    });
                }
                return ko.mapping.toJS(list, PropertyBase.mapping);
            };
            return {
                fixedQuestions: unwrap(self.fixedQuestions()),
                case_preload: unwrap(self.case_preload(), true),
                case_properties: unwrap(self.case_properties(), true)
            };
        }
    }

    var Careplan = function (params) {
        var self = this;
        self.mode = params.mode;
        self.caseType = params.caseType;
        self.home = params.home;
        self.save_url = params.save_url;
        self.questions = params.questions;
        self.reserved_words = params.reserved_words;
        self.moduleCaseTypes = params.moduleCaseTypes;
        self.propertiesMap = ko.mapping.fromJS(params.propertiesMap);

        self.transaction = CareplanTransaction.wrap({
            fixedQuestions: params.fixedQuestions,
            case_properties: params.customCaseUpdates,
            case_preload: params.case_preload
        }, self);

        var questionMap = {};
        _(self.questions).each(function (question) {
            questionMap[question.value] = question;
        });
        self.get_repeat_context = function (path) {
            if (path && questionMap[path]) {
                return questionMap[path].repeat;
            } else {
                return undefined;
            }
        };

        self.getQuestions = function (filter, excludeHidden, includeRepeat) {
            return CC_UTILS.getQuestions(self.questions, filter, excludeHidden, includeRepeat);
        };

        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: "You have unsaved changes",
            save: function () {
                var transaction = CareplanTransaction.unwrap(self.transaction);
                self.saveButton.ajax({
                    type: 'post',
                    url: self.save_url,
                    data: {
                        transaction: JSON.stringify(transaction)
                    },
                    dataType: 'json',
                    success: function (data) {
                        COMMCAREHQ.app_manager.updateDOM(data.update);
                    }
                });
            }
        });

        self.validate = ko.computed(function () {
            var has_dups = function (list) {
                 return _.find(_.values(list), function (count) {
                    return count > 1;
                });
            };
            var duplicate = has_dups(self.transaction.propertyPathCounts()) ||
                has_dups(self.transaction.propertyKeyCounts()) ||
                has_dups(self.transaction.preloadCounts());

            var isValid = duplicate === undefined;
            self.saveButton.fire(isValid ? 'enable' : 'disable');
            return  isValid;
        });

        self.change = function () {
            self.saveButton.fire('change');
            self.transaction.ensureBlankProperties();
        };

        self.init = function () {
            _.delay(function () {
                ko.applyBindings(self, self.home.get(0));
                self.home.on('textchange', 'input', self.change)
                     // all select2's are represented by an input[type="hidden"]
                     .on('change', 'select, input[type="hidden"]', self.change)
                     .on('click', 'a', self.change);
            });
            self.transaction.ensureBlankProperties();
        };
    };

    return {
        Careplan: Careplan
    };
}());

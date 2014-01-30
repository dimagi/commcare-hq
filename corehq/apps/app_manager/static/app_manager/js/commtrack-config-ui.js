/*globals $, COMMCAREHQ, _, ko, CC_UTILS, console*/

var DEFAULT_CONDITION = function (type) {
    'use strict';
    return {
        type: type,
        question: null,
        answer: null
    };
};

var CommTrackConfig = (function () {
    'use strict';

    var propertyDictToArray = function (required, property_dict, config) {
        var property_array = _(property_dict).map(function (value, key) {
            return {
                path: value,
                key: key,
                required: false
            };
        });
        property_array = _(property_array).sortBy(function (property) {
            return config.questionScores[property.path] * 2 + (property.required ? 0 : 1);
        });
        return required.concat(property_array);
    };

    var propertyArrayToDict = function (required, property_array) {
        var property_dict = {},
            extra_dict = {};
        _(property_array).each(function (case_property) {
            var key = case_property.key;
            var path = case_property.path;
            if (key || path) {
                if (_(required).contains(key) && case_property.required) {
                    extra_dict[key] = path;
                } else {
                    property_dict[key] = path;
                }
            }
        });
        return [property_dict, extra_dict];
    };

    var CasePropertyBase = {
        mapping: {
            include: ['key', 'path', 'required']
        },
        wrap: function (data, action) {
            var self = ko.mapping.fromJS(data, CaseProperty.mapping);
            self.action = action;
            self.isBlank = ko.computed(function () {
                return !self.key() && !self.path();
            });
            return self;
        }
    };

    var CaseProperty = {
        mapping: CasePropertyBase.mapping,
        wrap: function (data, action) {
            var self = CasePropertyBase.wrap(data, action);
            self.defaultKey = ko.computed(function () {
                var path = self.path() || '';
                var value = path.split('/');
                value = value[value.length-1];
                return value;
            });
            self.repeat_context = function () {
                return action.config.get_repeat_context(self.path());
            };
            self.validate = ko.computed(function () {
                if (self.path() || self.key()) {
                    if (action.propertyCounts()[self.key()] > 1) {
                        return "Property updated by two questions";
                    } else if (action.config.reserved_words.indexOf(self.key()) !== -1) {
                        return '<strong>' + self.key() + '</strong> is a reserved word';
                    } else if (self.repeat_context() && self.repeat_context() !== action.repeat_context()) {
                        return 'Inside the wrong repeat!';
                    }
                }
                return null;
            });
            return self;
        }
    };

    var CasePreloadProperty = {
        wrap: function (data, action) {
            var self = CasePropertyBase.wrap(data, action);
            self.defaultKey = ko.computed(function () {
                return '';
            });
            self.validateProperty = ko.computed(function () {
                if (self.path() || self.key()) {
                    if (action.config.reserved_words.indexOf(self.key()) !== -1) {
                        return '<strong>' + self.key() + '</strong> is a reserved word';
                    }
                }
                return null;
            });
            self.validateQuestion = ko.computed(function () {
                if (self.path()) {
                    if (action.preloadCounts()[self.path()] > 1) {
                        return "Two properties load to the same question";
                    }
                }
                return null;
            });
            return self;
        }
    };

    var  ActionBase = {
        validate: function (self, case_type, case_tag) {
            if (!case_type) {
                return "Case Type required";
            } else if (!case_tag) {
                return "Case Tag required";
            }
            if (!/^[a-zA-Z][\w_-]*(\/[a-zA-Z][\w_-]*)*$/.test(case_tag)) {
                return "Case Tag: only letters, numbers, '-', and '_' allowed";
            }
            var tags = self.config.caseConfigViewModel.getCaseTags('all');
            if (_.where(tags, {value: case_tag}).length > 1) {
                return "Case Tag already in use";
            }
            return null;
        },
        close_case: function (self) {
            return {
                read: function () {
                    if (self.close_condition) {
                        return self.close_condition.type() !== 'never';
                    } else {
                        return false;
                    }

                },
                write: function (value) {
                    self.close_condition.type(value ? 'always' : 'never');
                    self.config.saveButton.fire('change');
                }
            };
        },
        propertyCounts: function (self) {
            return function () {
                var count = {};
                _(self.case_properties()).each(function (p) {
                    var key = p.key();
                    if (!count.hasOwnProperty(key)) {
                        count[key] = 0;
                    }
                    return count[key] += 1;
                });
                return count;
            };
        }
    };

    var LoadUpdateCloseAction = {
        mapping: function (self) {
            return {
                include: ['case_type', 'case_tag', 'close_condition', 'show_product_stock'],
                preload: {
                    create: function (options) {
                        return CasePreloadProperty.wrap(options.data,  self.config);
                    }
                },
                update: {
                    create: function (options) {
                        return CaseProperty.wrap(options.data,  self);
                    }
                }
            };
        },
        wrap: function (data, config) {
            var self = {
                config: config,
                actionType: 'load'
            };
            self.config = config;
            ko.mapping.fromJS(data, LoadUpdateCloseAction.mapping(this), self);

            self.validate = ko.computed(function () {
                return ActionBase.validate(self, self.case_type(), self.case_tag());
            });

            self.close_case = ko.computed(ActionBase.close_case(self));

            self.case_properties = ko.computed(function () {
               return self.update();
            });

            self.propertyCounts = ko.computed(ActionBase.propertyCounts(self));

            self.preloadCounts = ko.computed(function () {
                var count = {};
                _(self.preload()).each(function (p) {
                    var path = p.path();
                    if (!count.hasOwnProperty(path)) {
                        count[path] = 0;
                    }
                    return count[path] += 1;
                });
                return count;
            });

            self.suggestedProperties = ko.computed(function () {
                if (_(config.propertiesMap).has(self.case_type())) {
                    return config.propertiesMap[self.case_type()]();
                } else {
                    return [];
                }
            });

            self.addProperty = function () {
                self.update.push(CaseProperty.wrap({
                    key: '',
                    path: '',
                    required: false
                }, self));
            };

            self.removeProperty = function (property) {
                self.update.remove(property);
            };

            self.addPreload = function () {
                self.preload.push(CasePreloadProperty.wrap({
                    key: '',
                    path: '',
                    required: false
                }, self));
            };

            self.removePreload = function (property) {
                self.preload.remove(property);
            };
            return self;
        }
    };

    var OpenCaseAction = {
        mapping: function (self) {
            return {
                include: ['case_type', 'case_name', 'case_tag', 'repeat_context', 'parent_tag', 'parent_reference_id', 'open_condition', 'close_condition'],
                case_properties: {
                    create: function (options) {
                        return CaseProperty.wrap(options.data,  self);
                    }
                }
            };
        },
        wrap: function (data, config) {
            var self = {
                config: config,
                actionType: 'open'
            };
            ko.mapping.fromJS(data, OpenCaseAction.mapping(self), self);

            self.validate = ko.computed(function () {
                return ActionBase.validate(self, self.case_type(), self.case_tag());
            });

            self.subcase = ko.observable(Boolean(self.parent_tag()));
            self.subcase.subscribe(function (subcase) {
                if (!subcase) {
                    self.parent_tag('');
                }
            });

            self.close_case = ko.computed(ActionBase.close_case(self));

            self.propertyCounts = ko.computed(ActionBase.propertyCounts(self));

            self.addProperty = function () {
                self.case_properties.push(CaseProperty.wrap({
                    key: '',
                    path: '',
                    required: false
                }, self));
            };

            self.removeProperty = function (property) {
                self.case_properties.remove(property);
            };

            return self;
        }
    };

    var FormActions = {
        mapping: function (self) {
            return {
                load_update_close_cases: {
                    create: function (options) {
                        return LoadUpdateCloseAction.wrap(options.data, self.config);
                    }
                },
                open_cases: {
                    create: function (options) {
                        return OpenCaseAction.wrap(options.data, self.config);
                    }
                }
            };
        },
        wrap: function (data, config) {
            var self = ko.mapping.fromJS(data, FormActions.mapping);
            self.config = config;

            return self;
        }
    };

    var Commtrack = function (params) {
        var self = this;

        self.home = params.home;
        self.questions = params.questions;
        self.edit = params.edit;
        self.save_url = params.save_url;
        // `requires` is a ko observable so it can be read by another UI
        self.requires = params.requires;
        self.caseType = params.caseType;
        self.reserved_words = params.reserved_words;
        self.moduleCaseTypes = params.moduleCaseTypes;
        self.propertiesMap = ko.mapping.fromJS(params.propertiesMap);

        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: "You have unchanged case settings",
            save: function () {
//                var requires = self.caseConfigViewModel.actionType() === 'update' ? 'case' : 'none';
//                var subcases;
//                if (self.caseConfigViewModel.actionType() === 'none') {
//                    subcases = [];
//                } else {
//                    subcases = _(self.caseConfigViewModel.subcases()).map(HQOpenSubCaseAction.from_case_transaction);
//                }
//                var actions = JSON.stringify(_(self.actions).extend(
//                    HQFormActions.from_case_transaction(self.caseConfigViewModel.case_transaction),
//                    {subcases: subcases}
//                ));
//
//                self.saveButton.ajax({
//                    type: 'post',
//                    url: self.save_url,
//                    data: {
//                        requires: requires,
//                        actions: actions
//                    },
//                    dataType: 'json',
//                    success: function (data) {
//                        COMMCAREHQ.app_manager.updateDOM(data.update);
//                        self.requires(requires);
//                        self.setPropertiesMap(data.propertiesMap);
//                    }
//                });
            }
        });

        self.caseTypes = _.unique(_(self.moduleCaseTypes).map(function (moduleCaseType) {
            return moduleCaseType.case_type;
        }));

        var questionMap = {};
        _(self.questions).each(function (question) {
            questionMap[question.value] = question;
        });
        self.get_repeat_context = function(path) {
            if (path && questionMap[path]) {
                return questionMap[path].repeat;
            } else {
                return undefined;
            }
        };

        var questionScores = {};
        _(self.questions).each(function (question, i) {
            questionScores[question.value] = i;
        });
        self.questionScores = questionScores;
        self.caseConfigViewModel = new CaseConfigViewModel(self, params);

        self.ensureBlankProperties = function () {
            self.caseConfigViewModel.ensureBlankProperties();
        };

        self.getQuestions = function (filter, excludeHidden, includeRepeat) {
            return CC_UTILS.getQuestions(self.questions, filter, excludeHidden, includeRepeat);
        };
        self.getAnswers = function (condition) {
            return CC_UTILS.getAnswers(self.questions, condition);
        };

        self.change = function () {
            self.saveButton.fire('change');
            self.ensureBlankProperties();
        };

        self.init = function () {
            var $home = $('#case-config-ko');
            _.delay(function () {
                ko.applyBindings(self, $home.get(0));
                $home.on('textchange', 'input', self.change)
                     // all select2's are represented by an input[type="hidden"]
                     .on('change', 'select, input[type="hidden"]', self.change)
                     .on('click', 'a', self.change);
                self.ensureBlankProperties();
            });
        };
    };

    var CaseConfigViewModel = function (config, params) {
        var self = this;

        self.config = config;
        self.edit = ko.observable(self.config.edit);
        self.moduleCaseTypes = config.moduleCaseTypes;
        self.caseTypes = _.unique(_(self.moduleCaseTypes).map(function (moduleCaseType) {
            return moduleCaseType.case_type;
        }));

        self.actions = FormActions.wrap(params.actions, self);

        self.getCaseTypeLabel = function (caseType) {
            var module_names = [], label;
            for (var i = 0; i < self.moduleCaseTypes.length; i++) {
                if (self.moduleCaseTypes[i].case_type === caseType) {
                    module_names.push(self.moduleCaseTypes[i].module_name);
                }
            }
            label = module_names.join(', ');
            if (caseType === self.config.caseType) {
                label = '*' + label;
            }
            return label;
        };

        self.getCaseTags = function (type) {
            var tags = [];
            var actions = [];
            if (type === 'all' || type === 'open') {
                actions = actions.concat(self.actions.open_cases());
            }
            if (type === 'all' || type === 'load') {
                actions = actions.concat(self.actions.load_update_close_cases());
            }
            for (var i = 0; i < actions.length; i++) {
                var tag = actions[i].case_tag();
                if (tag) {
                    tags.push({
                        value: tag,
                        label: tag
                    });
                }
            }
            return tags;
        };

        self.actionOptions = ko.computed(function () {
            var options = [];
            if (self.actions.load_update_close_cases().length <= 1) {
                options.push({
                    display: 'Load / Update / Close a case',
                    value: 'load'
                });
            }
            options.push({
                display: 'Open a Case',
                value: 'open'
            });
            return options;
        });
        
        self.ensureBlankProperties = function () {
            var items = [];
            var actions = self.actions.load_update_close_cases();
            for (var i = 0; i < actions.length; i++){
                items.push({
                    properties: actions[i].preload(),
                    addProperty: actions[i].addPreload
                });
                items.push({
                    properties: actions[i].update(),
                    addProperty: actions[i].addProperty
                });
            }
            actions = self.actions.open_cases();
            for (i = 0; i < actions.length; i++){
                items.push({
                    properties: actions[i].case_properties(),
                    addProperty: actions[i].addProperty
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

        self.addFormAction = function (action) {
            if (action.value === 'load') {
                $('#case-open-accordion').accordion({active: false});
                var index = self.actions.load_update_close_cases().length;
                self.actions.load_update_close_cases.push(LoadUpdateCloseAction.wrap({
                    case_type: config.caseType,
                    case_tag: 'load_' + config.caseType + index,
                    preload: [],
                    update: [],
                    close_condition: DEFAULT_CONDITION('never')
                }, self.config));
                if (index > 0) {
                    $('#case-load-accordion').accordion('activate', index);
                }
            } else if (action.value === 'open') {
                $('#case-load-accordion').accordion({active: false});
                var index = self.actions.open_cases().length;
                self.actions.open_cases.push(OpenCaseAction.wrap({
                    case_type: config.caseType,
                    case_name: '',
                    case_tag: 'open_' + config.caseType + '_' + index,
                    case_properties: [{
                            path: '',
                            key: 'name',
                            required: true
                        }],
                    repeat_context: '',
                    parent_tag: '',
                    parent_reference_id: '',
                    open_condition: DEFAULT_CONDITION('always'),
                    close_condition: DEFAULT_CONDITION('never')
                }, self.config));
                if (index > 0) {
                    $('#case-open-accordion').accordion('activate', index);
                }
            }
        };

        self.removeFormAction = function (action) {
            if (action.actionType === 'open') {
                self.actions.open_cases.remove(action);
            } else if (action.actionType === 'load') {
                self.actions.load_update_close_cases.remove(action);
            }
        };
    };

    return {
        Commtrack: Commtrack
    };
}());
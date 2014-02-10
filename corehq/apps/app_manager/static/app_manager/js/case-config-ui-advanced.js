/*globals $, COMMCAREHQ, _, ko, CC_UTILS, console*/

var AdvancedCase = (function () {
    'use strict';

    var DEFAULT_CONDITION = function (type) {
        return {
            type: type,
            question: null,
            answer: null
        };
    };

    var CaseConfig = function (params) {
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
        self.commtrack = params.commtrack_enabled;
        self.propertiesMap = ko.mapping.fromJS(params.propertiesMap);

        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: "You have unchanged case settings",
            save: function () {
                var actions = JSON.stringify(self.caseConfigViewModel.unwrap());
                self.saveButton.ajax({
                    type: 'post',
                    url: self.save_url,
                    data: {
                        actions: actions
                    },
                    dataType: 'json',
                    success: function (data) {
                        COMMCAREHQ.app_manager.updateDOM(data.update);
                        self.caseConfigViewModel.ensureBlankProperties();
                    }
                });
            }
        });

        var questionScores = {};
        _(self.questions).each(function (question, i) {
            questionScores[question.value] = i;
        });
        self.questionScores = questionScores;

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

        self.caseConfigViewModel = new CaseConfigViewModel(self, params);

        self.init = function () {
            var $home = $('#case-config-ko');
            _.delay(function () {
                ko.applyBindings(self, $home.get(0));
                $home.on('textchange', 'input', self.change)
                     // all select2's are represented by an input[type="hidden"]
                     .on('change', 'select, input[type="hidden"]', self.change)
                     .on('click', 'a', self.change);
                self.ensureBlankProperties();
                $('#case-configuration-tab').on('click', function () {
                    // re-apply accordion settings
                    _.delay(function () {
                        var options = {header: '> div > h3', heightStyle: 'content', collapsible: true, autoFill: true};
                        $('#case-open-accordion').accordion("destroy").accordion(options);
                        $('#case-load-accordion').accordion("destroy").accordion(options);
                    });
                });
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

        self.case_supports_products = function (case_type) {
            for (var i = 0; i < self.moduleCaseTypes.length; i++) {
                if (self.moduleCaseTypes[i].case_type === case_type &&
                    self.moduleCaseTypes[i].module_type === 'AdvancedModule') {
                    return true;
                }
            }
        };

        self.getCaseTags = function (type) {
            var tags = [];
            var actions = [];
            if (type === 'all' || type === 'open') {
                actions = actions.concat(self.open_cases());
            }
            if (type === 'all' || type === 'load') {
                actions = actions.concat(self.load_update_cases());
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

        self.load_update_cases = ko.observableArray(_(params.actions.load_update_cases).map(function (a) {
            a.preload = propertyDictToArray([], a.preload, config);
            a.case_properties = propertyDictToArray([], a.case_properties, config);
            return LoadUpdateAction.wrap(a, config);
        }));

        self.open_cases = ko.observableArray(_(params.actions.open_cases).map(function (a) {
            var required_properties = [{
                key: 'name',
                path: a.name_path,
                required: true
            }];
            a.case_properties = propertyDictToArray(required_properties, a.case_properties, config);
            return OpenCaseAction.wrap(a, config);
        }));

        self.actionOptions = ko.computed(function () {
            var options = [];
            if (self.load_update_cases().length <= 1) {
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

        self.renameCaseTag = function (oldTag, newTag) {
            var actions = self.open_cases();
            actions = actions.concat(self.load_update_cases());
            for (var i = 0; i < actions.length; i++) {
                var action = actions[i];
                if (action.case_tag() === oldTag) {
                    action.case_tag(newTag);
                }
                if (action.parent_tag() === oldTag) {
                    action.parent_tag(newTag);
                }
            }
        };

        self.ensureBlankProperties = function () {
            var items = [];
            var actions = self.load_update_cases();
            for (var i = 0; i < actions.length; i++){
                items.push({
                    properties: actions[i].preload(),
                    addProperty: actions[i].addPreload
                });
                items.push({
                    properties: actions[i].case_properties(),
                    addProperty: actions[i].addProperty
                });
            }
            actions = self.open_cases();
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
                var index = self.load_update_cases().length;
                self.load_update_cases.push(LoadUpdateAction.wrap({
                    case_type: config.caseType,
                    case_tag: 'load_' + config.caseType + index,
                    parent_tag: '',
                    preload: [],
                    case_properties: [],
                    close_condition: DEFAULT_CONDITION('never'),
                    show_product_stock: false
                }, self.config));
                if (index > 0) {
                    $('#case-load-accordion').accordion('activate', index);
                }
            } else if (action.value === 'open') {
                $('#case-load-accordion').accordion({active: false});
                var index = self.open_cases().length;
                self.open_cases.push(OpenCaseAction.wrap({
                    case_type: config.caseType,
                    name_path: '',
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
                self.open_cases.remove(action);
            } else if (action.actionType === 'load') {
                self.load_update_cases.remove(action);
            }
        };

        self.unwrap = function () {
            return {
                load_update_cases: _(self.load_update_cases()).map(LoadUpdateAction.unwrap),
                open_cases: _(self.open_cases()).map(OpenCaseAction.unwrap)
            };
        };
    };

    var  ActionBase = {
        validate: function (self, case_type, case_tag) {
            if (!self.config.caseConfigViewModel) {
                return;
            }
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
        },
        clean_condition: function (condition) {
            if (condition.type() !== 'if') {
                condition.question(null);
                condition.answer(null);
            }
        },
        header: function (action) {
            var nameSnip = "<%= action.case_tag() %> (<%= action.case_type() %>)";
            var closeSnip = "<% if (action.close_case()) { %> : close<% }%>";
            var spanSnip = '<span class="muted" style="font-weight: normal;">';
            if (action.actionType === 'open') {
                return _.template(nameSnip + spanSnip +
                    '<% if (action.subcase()) { %> : subacese of <span style="font-weight: bold;"><%= action.parent_tag() %></span><% } %>' +
                    closeSnip + "</span>",
                    action, {variable: 'action'});
            } else {
                return _.template(nameSnip + spanSnip +
                    "<% if (action.hasPreload()) { %> : load<% } %>" +
                    "<% if (action.hasCaseProperties()) { %> : update<% } %>" +
                    closeSnip + "</span>",
                    action, {variable: 'action'});
            }
        },
        suggestedProperties: function(action, allow_parent) {
            var properties = [];
            var propertiesMap = action.config.propertiesMap;
            var caseType = action.case_type();
            if (_(propertiesMap).has(caseType)) {
                properties = _.filter(propertiesMap[caseType](), function (p) {
                    return allow_parent ? true : p.indexOf('/') === -1;
                });
            }
            return properties;
        }
    };

    var LoadUpdateAction = {
        mapping: function (self) {
            return {
                include: ['case_type', 'case_tag', 'parent_tag', 'close_condition', 'show_product_stock'],
                preload: {
                    create: function (options) {
                        return CasePreloadProperty.wrap(options.data,  self);
                    }
                },
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
                actionType: 'load'
            };
            ko.mapping.fromJS(data, LoadUpdateAction.mapping(self), self);

            // for compatibility with common templates
            // template: case-config:condition
            self.allow = {
                repeats: function () {
                    return false;
                }
            };

            self.show_product_stock_var = ko.computed({
                read: function () {
                    return self.show_product_stock();
                },
                write: function (value) {
                    self.show_product_stock(value);
                    if (value) {
                        var newTag = 'case_' + self.case_type();
                        self.config.caseConfigViewModel.renameCaseTag(self.case_tag(), newTag);
                    }
                }
            });

            self.subcase = ko.computed({
                read: function () {
                    return self.parent_tag();
                },
                write: function (value) {
                    if (value) {
                        var parent = self.config.caseConfigViewModel.load_update_cases()[0];
                        if (parent) {
                            self.parent_tag(parent.case_tag());
                        }
                    } else {
                        self.parent_tag('');
                    }
                }
            });

            self.close_case = ko.computed(ActionBase.close_case(self));

            self.validate = ko.computed(function () {
                return ActionBase.validate(self, self.case_type(), self.case_tag());
            });

            // for compatibility with common templates
            self.case_preload = ko.computed(function () {
                return self.preload();
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
                return ActionBase.suggestedProperties(self, !self.subcase());
            });

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

            self.hasPreload = function() {
                return _.find(self.preload(), function (prop) { return !prop.isBlank(); });
            };

            self.hasCaseProperties = function() {
                return _.find(self.case_properties(), function (prop) { return !prop.isBlank(); });
            };

            self.header = ko.computed(function () {
                return ActionBase.header(self);
            });

            var add_circular = function() {
                // hacky way to prevent trying to access caseConfigViewModel before it is defined
                self.allow_product_stock = ko.computed(function () {
                    var supported = self.config.caseConfigViewModel.case_supports_products(self.case_type());
                    var loadupdatecases = self.config.caseConfigViewModel.load_update_cases;
                    return supported && loadupdatecases.indexOf(self) === loadupdatecases().length - 1;
                });

                self.disable_tag = ko.computed(function () {
                    return self.show_product_stock() && self.allow_product_stock();
                });
            };

            if (!self.config.caseConfigViewModel) {
                _.delay(add_circular);
            } else {
                add_circular();
            }

            return self;
        },
        unwrap: function (self) {
            var blank = function (prop) {
                return prop.isBlank();
            };
            self.preload.remove(blank);
            self.case_properties.remove(blank);
            ActionBase.clean_condition(self.close_condition);
            self.show_product_stock(self.disable_tag());
            var action = ko.mapping.toJS(self, LoadUpdateAction.mapping(self));

            action.preload = propertyArrayToDict([], action.preload)[0];
            action.case_properties = propertyArrayToDict([], action.case_properties)[0];
            return action;
        }
    };

    var OpenCaseAction = {
        mapping: function (self) {
            return {
                include: ['case_type', 'name_path', 'case_tag', 'repeat_context', 'parent_tag', 'parent_reference_id', 'open_condition', 'close_condition'],
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

            // for compatibility with common templates
            // template: case-config:condition
            self.allow = {
                repeats: function () {
                    return true;
                }
            };

            self.disable_tag = ko.computed(function () {
                return false;
            });

            self.suggestedProperties = ko.computed(function () {
                return ActionBase.suggestedProperties(self, false);
            });

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

            self.header = ko.computed(function () {
                return ActionBase.header(self);
            });

            self.propertyCounts = ko.computed(ActionBase.propertyCounts(self));

            self.name_path = ko.computed(function() {
                try {
                    return _(self.case_properties()).find(function (p) {
                        return p.key() === 'name' && p.required();
                    }).path();
                } catch (e) {
                    return null;
                }
            });

            self.repeat_context = function () {
                return self.config.get_repeat_context(self.name_path());
            };

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
        },
        unwrap: function (self) {
            self.case_properties.remove(function (prop) {
                return prop.isBlank();
            });
            var action = ko.mapping.toJS(self, OpenCaseAction.mapping(self));
            ActionBase.clean_condition(self.open_condition);
            ActionBase.clean_condition(self.close_condition);
            var x = propertyArrayToDict(['name'], action.case_properties);
            action.case_properties = x[0];
            action.name_path = x[1].name;
            return action;
        }
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

            // for compatibility with common templates
            self.case_transaction = {
                // template: case-config:case-properties:question
                allow: {
                    repeats: function () {
                        return action.allow.repeats();
                    }
                },
                // template: case-config:case-transaction:case-properties
                suggestedSaveProperties: self.action.suggestedProperties
            };

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
                    } else if (self.repeat_context() && self.repeat_context() !== self.action.repeat_context()) {
                        return 'Inside the wrong repeat!';
                    } else if (action.subcase() && _(self.key()).contains('/')) {
                        return 'Parent property references not allowed for subcases';
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

            // for compatibility with common templates
            self.case_transaction = {
                // template: case-config:case-properties:question
                allow: {
                    repeats: function () {
                        return action.allow.repeats();
                    }
                },
                // template: case-config:case-transaction:case-preload
                suggestedPreloadProperties: self.action.suggestedProperties
            };
            self.defaultKey = ko.computed(function () {
                return '';
            });
            self.validateProperty = ko.computed(function () {
                if (self.path() || self.key()) {
                    if (action.config.reserved_words.indexOf(self.key()) !== -1) {
                        return '<strong>' + self.key() + '</strong> is a reserved word';
                    } else if (action.subcase() && _(self.key()).contains('/')) {
                        return 'Parent property references not allowed for subcases';
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

    return {
        CaseConfig: CaseConfig
    };
}());
/*globals $, COMMCAREHQ, _, ko, CC_UTILS, console*/
var AdvancedCase = (function () {
    'use strict';

    var DEFAULT_CONDITION = function (type) {
        return {
            type: type,
            question: null,
            answer: null,
            operator: null
        };
    };

    var CaseConfig = function (params) {
        var self = this;

        self.home = params.home;
        self.questions = params.questions;
        self.save_url = params.save_url;
        self.caseType = params.caseType;
        self.module_id = params.module_id;
        self.reserved_words = params.reserved_words;
        self.moduleCaseTypes = params.moduleCaseTypes;
        // `requires` is a ko observable so it can be read by another UI
        self.requires = params.requires;
        self.commtrack = params.commtrack_enabled;
        self.programs = params.commtrack_programs;

        self.setPropertiesMap = function (propertiesMap) {
             self.propertiesMap = ko.mapping.fromJS(propertiesMap);
        };
        self.setPropertiesMap(params.propertiesMap);

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
                        var app_manager = hqImport('app_manager/js/app_manager.js');
                        app_manager.updateDOM(data.update);
                        self.caseConfigViewModel.ensureBlankProperties();
                        self.setPropertiesMap(data.propertiesMap);
                        self.requires(self.caseConfigViewModel.load_update_cases().length > 0 ? 'case' : 'none');
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

        self.getAutoSelectModes = function(action) {
            var index = self.caseConfigViewModel.load_update_cases.indexOf(action);
            var modes = [
                {
                    label: 'Raw',
                    value: 'raw'
                },
                {
                    label: 'User Data',
                    value: 'user'
                },
                {
                    label: 'Lookup Table',
                    value: 'fixture'
                },
                {
                    label: 'User Case',
                    value: 'usercase'
                }
            ];
            if (index > 0) {
                modes.push({
                    label: 'Case Index',
                    value: 'case'
                });
            }
            return modes;
        };

        self.case_supports_products = function (case_type) {
            for (var i = 0; i < self.moduleCaseTypes.length; i++) {
                if (self.moduleCaseTypes[i].case_type === case_type &&
                    self.moduleCaseTypes[i].module_type === 'AdvancedModule') {
                    return true;
                }
            }
        };

        self.module = (function () {
            var mod = _.findWhere(self.moduleCaseTypes, {id: self.module_id});
            mod.module_name = '* ' + mod.module_name;
            return mod;
        }());

        self.getModulesForCaseType = function (caseType, supportProducts) {
            var filter = {case_type: caseType};
            if (supportProducts) {
                filter.module_type = 'AdvancedModule';
            }
            var modules = _.where(self.moduleCaseTypes, filter);
            if (caseType === self.caseType) {
                modules = _.reject(modules, function(mod) {
                    return mod.id === self.module_id;
                });
                modules.splice(0, 0, self.module);
            }
            return modules;
        };

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

        self.applyAccordion = function (type, index) {
            _.each(type ? [type] : ['open', 'load'], function(t) {
                var selector = "#case-" + t + "-accordion";

                // Make sure all parents are set correctly so panels behave like an accordion
                $(selector + ' > .panel > .panel-collapse').collapse({
                    parent: selector,
                    toggle: false,
                });

                // Hide all panels, then show the requested one
                $(selector + ' .panel-collapse.in').collapse('hide')
                $(selector + ' > .panel:nth-child(' + (index + 1) + ') .panel-collapse').collapse('show');
            });
        };

        self.init = function () {
            var $home = $('#case-config-ko');
            _.delay(function () {
                $home.koApplyBindings(self);
                $home.on('textchange', 'input', self.change)
                     // all select2's are represented by an input[type="hidden"]
                     .on('change', 'select, input[type="hidden"]', self.change)
                     .on('click', 'a:not(.header)', self.change)
                     .on('change', 'input[type="checkbox"]', self.change);

                // https://gist.github.com/mkelly12/424774/#comment-92080
                $('#case-config-ko input').on('textchange', self.change);

                self.ensureBlankProperties();
                $('#case-configuration-tab').on('click', function () {
                    // Leave all the actions, collapsed, unless there's just
                    // one in the section, and then open it
                    if ($('#case-load-accordion > .panel').length === 1) {
                        self.applyAccordion('load', 0);
                    }
                    if ($('#case-open-accordion > .panel').length === 1) {
                        self.applyAccordion('open', 0);
                    }
                });
            });
        };
    };

    var CaseConfigViewModel = function (config, params) {
        var self = this;

        self.config = config;

        self.getCaseTags = function (type, action) {
            var tags = [];
            var actions = [];
            if (type === 'all') {
                actions = actions.concat(self.open_cases());
                actions = actions.concat(self.load_update_cases());
            }
            if (type === 'subcase') {
                actions = actions.concat(self.load_update_cases());
                // only allow creating subcases of actions before this one
                var index = self.open_cases.indexOf(action);
                if (index > 0) {
                    actions = actions.concat(self.open_cases.slice(0, index));
                }
            }
            if (type === 'auto-select') {
                // only allow auto-selecting based off loaded actions before this one
                var index = self.load_update_cases.indexOf(action);
                if (index > 0) {
                    actions = actions.concat(self.load_update_cases.slice(0, index));
                }
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

        self.getActionFromTag = function (tag) {
            var action = _.find(self.open_cases(), function (a) {
                return a.case_tag() === tag;
            });
            if (action) {
                return action;
            }
            action = _.find(self.load_update_cases(), function (a) {
                return a.case_tag() === tag;
            });
            return action;
        };

        self.load_update_cases = ko.observableArray(_(params.actions.load_update_cases).map(function (a) {
            var preload = CC_UTILS.propertyDictToArray([], a.preload, config, true);
            var case_properties = CC_UTILS.propertyDictToArray([], a.case_properties, config);
            a.preload = [];
            a.case_properties = [];
            var action = LoadUpdateAction.wrap(a, config);
            // add these after to avoid errors caused by 'action.suggestedProperties' being accessed
            // before it is defined
            _(case_properties).each(function (p) {
                action.case_properties.push(CaseProperty.wrap(p, action));
            });
            _(preload).each(function (p) {
                action.preload.push(CasePreloadProperty.wrap(p, action));
            });
            return action;
        }));

        self.open_cases = ko.observableArray(_(params.actions.open_cases).map(function (a) {
            var required_properties = [{
                key: 'name',
                path: a.name_path,
                required: true
            }];
            var case_properties = CC_UTILS.propertyDictToArray(required_properties, a.case_properties, config);
            a.case_properties = [];
            var action = OpenCaseAction.wrap(a, config);
            // add these after to avoid errors caused by 'action.suggestedProperties' being accessed
            // before it is defined
            _(case_properties).each(function (p) {
                action.case_properties.push(CaseProperty.wrap(p, action));
            });
            return action;
        }));

        self.actionOptions = ko.observableArray([
            {
                display: 'Load / Update / Close a case',
                value: 'load'
            },
            {
                display: 'Automatic Case Selection',
                value: 'auto_select'
            },
            {
                display: '---',
                value: 'separator'
            },
            {
                display: 'Open a Case',
                value: 'open'
            }
        ]);

        self.renameCaseTag = function (oldTag, newTag, parentOnly) {
            var actions = self.load_update_cases();
            var action;
            for (var i = 0; i < actions.length; i++) {
                action = actions[i];
                if (!parentOnly && action.case_tag() === oldTag) {
                    action.case_tag(newTag);
                }
                if (action.case_index.tag() === oldTag) {
                    action.case_index.tag(newTag);
                }
            }
            actions = self.open_cases();
            for (i = 0; i < actions.length; i++) {
                action = actions[i];
                if (!parentOnly && action.case_tag() === oldTag) {
                    action.case_tag(newTag);
                }
                for (var j = 0; j < action.case_indices.length; j++) {
                    var caseIndex = action.case_indices[j];
                    if (caseIndex.tag() === oldTag) {
                        caseIndex.tag(newTag);
                    }
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
            if (action.value === 'load' || action.value === 'auto_select') {
                var index = self.load_update_cases().length;
                var tag_prefix = action.value === 'auto_select'? 'auto' : '';
                var action_data = {
                    case_type: config.caseType,
                    details_module: null,
                    case_tag: tag_prefix + 'load_' + config.caseType + index,
                    case_index: {
                        tag: '',
                        reference_id: 'parent',
                        relationship: 'child'
                    },
                    preload: [],
                    case_properties: [],
                    close_condition: DEFAULT_CONDITION('never'),
                    show_product_stock: false,
                    product_program: '',
                    auto_select: null
                };
                if (action.value === 'auto_select') {
                    action_data.auto_select = {
                        mode: '',
                        value_source: '',
                        value_key: ''
                    };

                }
                self.load_update_cases.push(LoadUpdateAction.wrap(action_data, self.config));
                self.config.applyAccordion('load', index);
            } else if (action.value === 'open') {
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
                    case_indices: [],
                    open_condition: DEFAULT_CONDITION('always'),
                    close_condition: DEFAULT_CONDITION('never')
                }, self.config));
                self.config.applyAccordion('open', index);
            }
        };

        self.removeFormAction = function (action) {
            if (action.actionType === 'open') {
                self.open_cases.remove(action);
            } else if (action.actionType === 'load') {
                var index = self.config.caseConfigViewModel.load_update_cases.indexOf(action),
                    potential_child;
                self.load_update_cases.remove(action);

                // remove references to deleted action in other load actions
                var loadUpdateCases = self.config.caseConfigViewModel.load_update_cases();
                for (var i = index; i < loadUpdateCases.length; i++) {
                    potential_child = loadUpdateCases[i];
                    for (var j = 0; j < potential_child.parents.length; j++) {
                        var caseIndex = potential_child.parents[i];
                        if (caseIndex.tag() === action.case_tag()) {
                            caseIndex.tag('');
                        }

                    }
                }
            }
        };

        self.unwrap = function () {
            return {
                load_update_cases: _(self.load_update_cases()).map(LoadUpdateAction.unwrap),
                open_cases: _(self.open_cases()).map(OpenCaseAction.unwrap)
            };
        };
    };

    var CaseIndex = {
        mapping: {
            include: ['tag', 'reference_id', 'relationship']
        },
        wrap: function (data) {
            var self = ko.mapping.fromJS(data, CaseIndex.mapping);
            self.relationship.subscribe(function (value) {
                if (value === 'extension' && self.reference_id() === 'parent') {
                    self.reference_id('host');
                } else if (value === 'child' && self.reference_id() === 'host') {
                    self.reference_id('parent');
                }
            });
            return self;
        }
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
                condition.operator(null);
            }
        },
        header: function (action) {
            var nameSnip = "<%= action.case_tag() %> (<%= action.case_type() %>)";
            var closeSnip = "<% if (action.close_case()) { %> : close<% }%>";
            var spanSnip = '<span class="text-muted" style="font-weight: normal;">';
            if (action.actionType === 'open') {
                return _.template(
                    nameSnip + spanSnip +
                    '<% if (action.parent_tags()) { %> : ' +
                    'subcase of <span style="font-weight: bold;"><%= action.parent_tags() %></span>' +
                    '<% } %>' + closeSnip + "</span>",
                    action, {variable: 'action'});
            } else {
                if (action.auto_select) {
                    nameSnip = "<%= action.case_tag() %> (autoselect mode: <%= action.auto_select.mode() %>)";
                }
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
        },
        relationshipTypes: ['child', 'extension']
    };

    var LoadUpdateAction = {
        mapping: function (self) {
            return {
                include: [
                    'case_type',
                    'details_module',
                    'case_tag',
                    'close_condition',
                    'show_product_stock',
                    'product_program'
                ],
                preload: {
                    create: function (options) {
                        return CasePreloadProperty.wrap(options.data,  self);
                    }
                },
                case_properties: {
                    create: function (options) {
                        return CaseProperty.wrap(options.data,  self);
                    }
                },
                auto_select: {
                    create: function (options) {
                        if (options.data) {
                            return AutoSelect.wrap(options.data, self);
                        } else {
                            return null;
                        }
                    }
                },
                case_index: {
                    create: function (options) {
                        return CaseIndex.wrap(options.data);
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

            self.available_modules = ko.computed(function () {
                return config.getModulesForCaseType(self.case_type(), self.show_product_stock());
            });

            if (self.auto_select) {
                self.auto_select.mode.subscribe(function (value) {
                    // suggestedProperties need to be those of case type "commcare-user"
                    if (value === 'usercase') {
                        self.case_type('commcare-user');
                    }
                });
            }

            self.show_product_stock_var = ko.computed({
                read: function () {
                    return self.show_product_stock();
                },
                write: function (value) {
                    self.show_product_stock(value);
                    if (value) {
                        var newTag = 'case_' + self.case_type();
                        self.config.caseConfigViewModel.renameCaseTag(self.case_tag(), newTag);
                    } else {
                        self.product_program('');
                    }
                }
            });

            self.subcase = ko.computed({
                read: function () {
                    return self.case_index.tag();
                },
                write: function (value) {
                    if (value) {
                        var index = self.config.caseConfigViewModel.load_update_cases.indexOf(self);
                        if (index > 0) {
                            var parent = self.config.caseConfigViewModel.load_update_cases()[index - 1];
                            self.case_index.tag(parent.case_tag());
                        }
                    } else {
                        self.case_index.tag('');
                    }
                }
            });

            self.case_tag.extend({ withPrevious: 1 });
            self.case_tag.subscribe(function (tag) {
                self.config.caseConfigViewModel.renameCaseTag(self.case_tag.previous(), tag, true);
            });

            self.close_case = ko.computed(ActionBase.close_case(self));

            self.validate = ko.computed(function () {
                if (self.auto_select){
                    var mode = self.auto_select.mode();
                    var value_source = self.auto_select.value_source();
                    var value_key = self.auto_select.value_key();
                    if (!mode) {
                        return "Autoselect mode required";
                    } else if (!value_key && mode !== 'usercase') {
                        return 'Property required';
                    } else if (!value_source) {
                        if (mode === 'case') {
                            return 'Case required';
                        } else if (mode === 'fixture') {
                            return 'Lookup table tag required';
                        }
                    }
                    return null;
                } else {
                    return ActionBase.validate(self, self.case_type(), self.case_tag());
                }
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
                self.config.saveButton.fire('change');
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
                self.config.saveButton.fire('change');
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

            self.relationshipTypes = ActionBase.relationshipTypes;

            var add_circular = function() {
                // hacky way to prevent trying to access caseConfigViewModel before it is defined
                self.allow_product_stock = ko.computed(function () {
                    var supported = self.config.case_supports_products(self.case_type());
                    var loadupdatecases = self.config.caseConfigViewModel.load_update_cases;
                    return supported && loadupdatecases.indexOf(self) === loadupdatecases().length - 1;
                });

                self.disable_tag = ko.computed(function () {
                    return self.show_product_stock() && self.allow_product_stock();
                });

                self.auto_select_modes = ko.computed(function () {
                    return config.getAutoSelectModes(self);
                });
                self.validate_subcase = ko.computed(function () {
                    if (!self.config.caseConfigViewModel) {
                        return;
                    }
                    if (!self.case_index.tag()) {
                        return null;
                    }
                    var parent = self.config.caseConfigViewModel.getActionFromTag(self.case_index.tag());
                    if (!parent) {
                        return "Subcase parent reference is missing";
                    } else if (!self.case_index.reference_id()) {
                        return 'Parent "' + self.case_index.tag() + '" reference ID required for subcases';
                    } else if (parent.actionType === 'open') {
                        if (!parent.repeat_context()) {
                            return null;
                        } else if (!self.repeat_context() ||
                            // manual string startsWith
                            self.repeat_context().lastIndexOf(parent.repeat_context(), 0) === 0) {
                            return 'Subcase must be in same repeat context as parent "' + self.case_index.tag() + '".';
                        }
                    }
                    return null;

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

            action.preload = CC_UTILS.preloadArrayToDict(action.preload);
            action.case_properties = CC_UTILS.propertyArrayToDict([], action.case_properties)[0];
            return action;
        }
    };

    var OpenCaseAction = {
        mapping: function (self) {
            return {
                include: [
                    'case_type',
                    'name_path',
                    'case_tag',
                    'open_condition',
                    'close_condition'
                ],
                case_properties: {
                    create: function (options) {
                        return CaseProperty.wrap(options.data,  self);
                    }
                },
                case_indices: {
                    create: function (options) {
                        return CaseIndex.wrap(options.data, self);
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
                return CC_UTILS.filteredSuggestedProperties(
                    ActionBase.suggestedProperties(self, false),
                    self.case_properties()
                );
            });

            self.validate = ko.computed(function () {
                return ActionBase.validate(self, self.case_type(), self.case_tag());
            });

            self.parent_tags = function () {
                var tags = [];
                for (var i = 0; i < self.case_indices().length; i++) {
                    tags.push(self.case_indices()[i].tag());
                }
                return tags.join(', ');
            };

            self.subcase = ko.computed({
                read: function () {
                    return (self.case_indices().length > 0);
                },
                write: function (value) {
                    if (value) {
                        self.case_indices.push(CaseIndex.wrap({
                            tag: 'Select parent',
                            reference_id: 'parent',
                            relationship: 'child'
                        }));
                    } else {
                        self.case_indices.removeAll();
                    }
                }
            });

            self.addCaseIndex = function () {
                /**
                 * Copy newCaseIndex form values, and push them to parents array.
                 *
                 * Reference in 'data-bind="with: newCaseIndex"' does not change, so
                 * we need to copy values to another instance, and then reset the
                 * values in the form.
                 */
                self.case_indices.push(CaseIndex.wrap({
                    tag: '',
                    reference_id: 'parent',
                    relationship: 'child'
                }));
            };

            self.removeCaseIndex = function (viewModel) {
                self.case_indices.remove(viewModel);
            };

            self.case_tag.extend({ withPrevious: 1 });
            self.case_tag.subscribe(function (tag) {
                self.config.caseConfigViewModel.renameCaseTag(self.case_tag.previous(), tag, true);
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
                self.config.saveButton.fire('change');
            };

            self.relationshipTypes = ActionBase.relationshipTypes;

            var add_circular = function () {
                self.allow_subcase = ko.computed(function () {
                    return self.case_indices || self.config.caseConfigViewModel.getCaseTags('subcase', self).length > 0;
                });
                self.validate_subcase = ko.computed(function () {
                    if (!self.config.caseConfigViewModel) {
                        return;
                    }
                    if (!self.case_indices) {
                        return null;
                    }
                    for (var i = 0; i < self.case_indices.length; i++) {
                        var caseIndex = self.case_indices[i];
                        var parent = self.config.caseConfigViewModel.getActionFromTag(caseIndex.tag());
                        if (!parent) {
                            return "Subcase parent reference is missing";
                        } else if (!caseIndex.reference_id()) {
                            return 'Parent "' + caseIndex.tag() + '" reference ID required for subcases';
                        } else if (parent.actionType === 'open') {
                            if (!parent.repeat_context()) {
                                return null;
                            } else if (!self.repeat_context() ||
                                // manual string startsWith
                                self.repeat_context().lastIndexOf(parent.repeat_context(), 0) === 0) {
                                return 'Subcase must be in same repeat context as parent "' + caseIndex.tag() + '".';
                            }
                        }
                    }
                    return null;
                });
            };
            // hacky way to prevent trying to access caseConfigViewModel before it is defined
            if (!self.config.caseConfigViewModel) {
                _.delay(add_circular);
            } else {
                add_circular();
            }

            return self;
        },
        unwrap: function (self) {
            self.case_properties.remove(function (prop) {
                return prop.isBlank();
            });
            if (self.case_indices().length > 0 && !self.allow_subcase()) {
                self.case_indices.removeAll();
            }
            ActionBase.clean_condition(self.open_condition);
            ActionBase.clean_condition(self.close_condition);
            var action = ko.mapping.toJS(self, OpenCaseAction.mapping(self));
            var x = CC_UTILS.propertyArrayToDict(['name'], action.case_properties);
            action.case_properties = x[0];
            action.name_path = x[1].name;
            action.repeat_context = self.repeat_context();
            return action;
        }
    };

    var AutoSelect = {
        mapping: {
            include: ['mode', 'value_source', 'value_key']
        },
        wrap: function (data, action) {
            var self = ko.mapping.fromJS(data, AutoSelect.mapping);
            self.action = action;
            self.isBlank = ko.computed(function () {
                return !self.value_source() && !self.value_key();
            });

            self.mode.subscribe(function(value) {
                self.value_source('');
                self.value_key('');
            });
            return self;
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
                suggestedSaveProperties: ko.computed(function () {
                    return CC_UTILS.filteredSuggestedProperties(
                        self.action.suggestedProperties(),
                        self.action.case_properties()
                    );
                })
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
                suggestedPreloadProperties: ko.computed(function () {
                    return CC_UTILS.filteredSuggestedProperties(
                        self.action.suggestedProperties(),
                        self.action.preload()
                    );
                })
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

    return {
        CaseConfig: CaseConfig
    };
}());

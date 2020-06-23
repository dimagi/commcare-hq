hqDefine('app_manager/js/forms/advanced/case_config_ui', function () {
    'use strict';

    $(function () {
        var caseConfigUtils = hqImport('app_manager/js/case_config_utils'),
            caseProperty = hqImport("app_manager/js/forms/advanced/case_properties").caseProperty,
            casePreloadProperty = hqImport("app_manager/js/forms/advanced/case_properties").casePreloadProperty,
            loadUpdateAction = hqImport("app_manager/js/forms/advanced/actions").loadUpdateAction,
            openCaseAction = hqImport("app_manager/js/forms/advanced/actions").openCaseAction,
            initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;

        var DEFAULT_CONDITION = function (type) {
            return {
                type: type,
                question: null,
                answer: null,
                operator: null,
            };
        };

        var caseConfig = function (params) {
            var self = {};
            self.makePopover = function () {
                $('.property-description').closest('.read-only').popover({
                    'trigger': 'hover',
                    'placement': 'bottom',
                    'sanitize': false,
                });
            };

            self.home = params.home;
            self.questions = ko.observable(params.questions);
            self.save_url = params.save_url;
            self.caseType = params.caseType;
            self.module_id = params.module_id;
            self.reserved_words = params.reserved_words;
            self.moduleCaseTypes = params.moduleCaseTypes;
            // `requires` is a ko observable so it can be read by another UI
            self.requires = params.requires;
            self.commtrack = params.commtrack_enabled;
            self.programs = params.commtrack_programs;
            self.isShadowForm = params.isShadowForm;

            self.setPropertiesMap = function (propertiesMap) {
                self.propertiesMap = ko.mapping.fromJS(propertiesMap);
            };
            self.setPropertiesMap(params.propertiesMap);

            self.descriptionDict = params.propertyDescriptions;

            self.saveButton = hqImport("hqwebapp/js/main").initSaveButton({
                unsavedMessage: "You have unchanged case settings",
                save: function () {
                    var actions = JSON.stringify(self.caseConfigViewModel.unwrap());
                    self.saveButton.ajax({
                        type: 'post',
                        url: self.save_url,
                        data: {
                            actions: actions,
                        },
                        dataType: 'json',
                        success: function (data) {
                            var app_manager = hqImport('app_manager/js/app_manager');
                            app_manager.updateDOM(data.update);
                            self.setPropertiesMap(data.propertiesMap);
                            self.requires(self.caseConfigViewModel.load_update_cases().length > 0 ? 'case' : 'none');
                        },
                    });
                },
            });

            var questionScores = {};
            _(self.questions()).each(function (question, i) {
                questionScores[question.value] = i;
            });
            self.questionScores = questionScores;

            self.caseTypes = _.unique(_(self.moduleCaseTypes).map(function (moduleCaseType) {
                return moduleCaseType.case_type;
            }));

            self.getAutoSelectModes = function (action) {
                var index = self.caseConfigViewModel.load_update_cases.indexOf(action);
                var modes = [{
                    label: gettext('Raw'),
                    value: 'raw',
                }, {
                    label: gettext('User Data'),
                    value: 'user',
                }, {
                    label: gettext('Lookup Table'),
                    value: 'fixture',
                }, {
                    label: gettext('User Properties'),
                    value: 'usercase',
                }];
                if (index > 0) {
                    modes.push({
                        label: gettext('Case Index'),
                        value: 'case',
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
                var mod = _.findWhere(self.moduleCaseTypes, {
                    id: self.module_id,
                });
                mod.module_name = '* ' + mod.module_name;
                return mod;
            }());

            self.getModulesForCaseType = function (caseType, supportProducts) {
                var filter = {
                    case_type: caseType,
                };
                if (supportProducts) {
                    filter.module_type = 'AdvancedModule';
                }
                var modules = _.where(self.moduleCaseTypes, filter);
                if (caseType === self.caseType) {
                    modules = _.reject(modules, function (mod) {
                        return mod.id === self.module_id;
                    });
                    modules.splice(0, 0, self.module);
                }
                return modules;
            };

            self.questionMap = {};
            var _buildQuestionMap = function () {
                self.questionMap = {};
                _(self.questions()).each(function (question) {
                    self.questionMap[question.value] = question;
                });
            };
            _buildQuestionMap();
            self.questions.subscribe(_buildQuestionMap);

            self.get_repeat_context = function (path) {
                if (path && self.questionMap[path]) {
                    return self.questionMap[path].repeat;
                } else {
                    return undefined;
                }
            };

            self.getQuestions = function (filter, excludeHidden, includeRepeat) {
                return caseConfigUtils.getQuestions(self.questions(), filter, excludeHidden, includeRepeat);
            };

            self.refreshQuestions = function (url, formUniqueId, event) {
                return caseConfigUtils.refreshQuestions(self.questions, url, formUniqueId, event);
            };

            self.getAnswers = function (condition) {
                return caseConfigUtils.getAnswers(self.questions(), condition);
            };

            self.change = function () {
                self.saveButton.fire('change');
            };

            self.caseConfigViewModel = caseConfigViewModel(self, params);

            self.applyAccordion = function (type, index) {
                _.each(type ? [type] : ['open', 'load'], function (t) {
                    var selector = "#case-" + t + "-accordion";

                    // Make sure all parents are set correctly so panels behave like an accordion
                    $(selector + ' > .panel > .panel-collapse').collapse({
                        parent: selector,
                        toggle: false,
                    });

                    // Hide all panels, then show the requested one
                    $(selector + ' .panel-collapse.in').collapse('hide');
                    $(selector + ' > .panel:nth-child(' + (index + 1) + ') .panel-collapse').collapse('show');
                });
            };

            self.initAccordion = function () {
                // Leave all the actions, collapsed, unless there's just
                // one in the section, and then open it
                if ($('#case-load-accordion > .panel').length === 1) {
                    self.applyAccordion('load', 0);
                }
                if ($('#case-open-accordion > .panel').length === 1) {
                    self.applyAccordion('open', 0);
                }
            };

            self.init = function () {
                var $home = self.home;
                _.delay(function () {
                    $home.koApplyBindings(self);
                    $home.on('textchange', 'input', self.change)
                        // all select2's are represented by an input[type="hidden"]
                        .on('change', 'select, input[type="hidden"]', self.change)
                        .on('click', 'a:not(.header)', self.change)
                        .on('change', 'input[type="checkbox"]', self.change);

                    // https://gist.github.com/mkelly12/424774/#comment-92080
                    $home.find('input').on('textchange', self.change);

                    self.initAccordion();
                    $('#case-configuration-tab').on('click', function () {
                        self.initAccordion();
                    });

                    $('.hq-help-template').each(function () {
                        hqImport("hqwebapp/js/main").transformHelpTemplate($(this), true);
                    });
                });
            };
            return self;
        };

        var caseConfigViewModel = function (caseConfig, params) {
            var self = {};

            self.caseConfig = caseConfig;
            self.hasPrivilege = true;

            self.getCaseTags = function (type, action) {
                var tags = [],
                    actions = [],
                    index;
                if (type === 'all') {
                    actions = actions.concat(self.open_cases());
                    actions = actions.concat(self.load_update_cases());
                }
                if (type === 'subcase') {
                    actions = actions.concat(self.load_update_cases());
                    // only allow creating subcases of actions before this one
                    index = self.open_cases.indexOf(action);
                    if (index > 0) {
                        actions = actions.concat(self.open_cases.slice(0, index));
                    }
                }
                if (type === 'auto-select') {
                    // only allow auto-selecting based off loaded actions before this one
                    index = self.load_update_cases.indexOf(action);
                    if (index > 0) {
                        actions = actions.concat(self.load_update_cases.slice(0, index));
                    }
                }

                for (var i = 0; i < actions.length; i++) {
                    var tag = actions[i].case_tag();
                    if (tag) {
                        tags.push({
                            value: tag,
                            label: tag,
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
                var preload = caseConfigUtils.propertyDictToArray([], a.preload, caseConfig, true);
                var case_properties = caseConfigUtils.propertyDictToArray([], a.case_properties, caseConfig);
                a.preload = [];
                a.case_properties = [];
                var action = loadUpdateAction.wrap(a, caseConfig);
                // add these after to avoid errors caused by 'action.suggestedProperties' being accessed
                // before it is defined
                _(case_properties).each(function (p) {
                    action.case_properties.push(caseProperty.wrap(p, action));
                });

                // needed for compatibility with shared templates
                action.searchAndFilter = false;
                action.visible_case_properties = ko.computed(function () {
                    return action.case_properties();
                });

                _(preload).each(function (p) {
                    action.preload.push(casePreloadProperty.wrap(p, action));
                });
                return action;
            }));

            self.open_cases = ko.observableArray(_(params.actions.open_cases).map(function (a) {
                var required_properties = [{
                    key: 'name',
                    path: a.name_path,
                    required: true,
                }];
                var case_properties = caseConfigUtils.propertyDictToArray(required_properties, a.case_properties, caseConfig);
                a.case_properties = [];
                var action = openCaseAction.wrap(a, caseConfig);
                // add these after to avoid errors caused by 'action.suggestedProperties' being accessed
                // before it is defined
                _(case_properties).each(function (p) {
                    action.case_properties.push(caseProperty.wrap(p, action));
                });

                // needed for compatibility with shared templates
                action.searchAndFilter = false;
                action.visible_case_properties = ko.computed(function () {
                    return action.case_properties();
                });

                return action;
            }));

            var _actions = [{
                display: gettext('Load / Update / Close a case'),
                value: 'load',
            }, {
                display: gettext('Automatic Case Selection'),
                value: 'auto_select',
            }, {
                display: gettext('Load Case From Fixture'),
                value: 'load_case_from_fixture',
            } ];
            if (!self.caseConfig.isShadowForm) {
                _actions = _actions.concat([{
                    display: '---',
                    value: 'separator',
                }, {
                    display: gettext('Open a Case'),
                    value: 'open',
                } ]);
            }
            self.actionOptions = ko.observableArray(_actions);

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

            self.addFormAction = function (action) {
                var index;
                if (action.value === 'load' || action.value === 'auto_select' || action.value === 'load_case_from_fixture') {
                    index = self.load_update_cases().length;
                    var tag_prefix = action.value === 'auto_select' ? 'auto' : '',
                        action_data = {
                            case_type: caseConfig.caseType,
                            details_module: null,
                            case_tag: tag_prefix + 'load_' + caseConfig.caseType + index,
                            case_index: {
                                tag: '',
                                reference_id: 'parent',
                                relationship: 'child',
                            },
                            preload: [],
                            case_properties: [],
                            close_condition: DEFAULT_CONDITION('never'),
                            show_product_stock: false,
                            product_program: '',
                            auto_select: null,
                            load_case_from_fixture: null,
                        };
                    if (action.value === 'auto_select') {
                        action_data.auto_select = {
                            mode: '',
                            value_source: '',
                            value_key: '',
                        };
                    } else if (action.value === 'load_case_from_fixture') {
                        action_data.load_case_from_fixture = {
                            fixture_nodeset: '',
                            fixture_tag: '',
                            fixture_variable: '',
                            case_property: '',
                            auto_select: false,
                            auto_select_fixture: false,
                            arbitrary_datum_id: '',
                            arbitrary_datum_function: '',
                        };
                    }
                    self.load_update_cases.push(loadUpdateAction.wrap(action_data, self.caseConfig));
                    self.caseConfig.applyAccordion('load', index);
                } else if (action.value === 'open') {
                    index = self.open_cases().length;
                    self.open_cases.push(openCaseAction.wrap({
                        case_type: caseConfig.caseType,
                        name_path: '',
                        case_tag: 'open_' + caseConfig.caseType + '_' + index,
                        case_properties: [{
                            path: '',
                            key: 'name',
                            required: true,
                        }],
                        repeat_context: '',
                        case_indices: [],
                        open_condition: DEFAULT_CONDITION('always'),
                        close_condition: DEFAULT_CONDITION('never'),
                    }, self.caseConfig));
                    self.caseConfig.applyAccordion('open', index);
                }
            };

            self.removeFormAction = function (action) {
                if (action.actionType === 'open') {
                    self.open_cases.remove(action);
                } else if (action.actionType === 'load') {
                    var index = self.caseConfig.caseConfigViewModel.load_update_cases.indexOf(action),
                        potential_child;
                    self.load_update_cases.remove(action);

                    // remove references to deleted action in subsequent load actions
                    var loadUpdateCases = self.caseConfig.caseConfigViewModel.load_update_cases();
                    for (var i = index; i < loadUpdateCases.length; i++) {
                        var caseIndex = loadUpdateCases[i].case_index;
                        if (caseIndex.tag() === action.case_tag()) {
                            caseIndex.tag('');
                        }
                    }
                }
                self.caseConfig.saveButton.fire('change');
            };

            self.unwrap = function () {
                return {
                    load_update_cases: _(self.load_update_cases()).map(loadUpdateAction.unwrap),
                    open_cases: _(self.open_cases()).map(openCaseAction.unwrap),
                };
            };
            return self;
        };

        if (initial_page_data('has_form_source')) {
            var caseConfig = caseConfig(_.extend({}, initial_page_data("case_config_options"), {
                home: $('#case-config-ko'),
                requires: ko.observable(initial_page_data("form_requires")),
            }));
            caseConfig.init();

            if (initial_page_data("schedule_options")) {
                var VisitScheduler = hqImport('app_manager/js/visit_scheduler');
                var visitScheduler = VisitScheduler.schedulerModel(_.extend({}, initial_page_data("schedule_options"), {
                    home: $('#visit-scheduler'),
                }));
                visitScheduler.init();
            }
        }
    });
});

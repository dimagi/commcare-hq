hqDefine('app_manager/js/forms/case_config_ui', function () {
    "use strict";
    $(function () {
        var caseConfigUtils = hqImport('app_manager/js/case_config_utils'),
            initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
            privileges = initial_page_data('add_ons_privileges'),
            toggles = hqImport("hqwebapp/js/toggles");
        var action_names = ["open_case", "update_case", "close_case", "case_preload",
            // Usercase actions are managed in the User Properties tab.
            "usercase_update", "usercase_preload",
        ];

        var caseConfig = function (params) {
            var self = {};
            self.makePopover = function () {
                $('.property-description').closest('.read-only').popover({
                    'trigger': 'hover',
                    'placement': 'auto right',
                });
            };

            self.home = params.home;
            self.actions = (function (a) {
                var actions = {};
                _(action_names).each(function (action_name) {
                    actions[action_name] = a[action_name];
                });
                actions.subcases = a.subcases;
                return actions;
            }(params.actions));
            self.questions = ko.observable(params.questions);
            self.save_url = params.save_url;
            // `requires` is a ko observable so it can be read by another UI
            self.requires = params.requires;
            self.caseType = params.caseType;
            self.reserved_words = params.reserved_words;
            self.valid_index_names = params.valid_index_names;
            self.moduleCaseTypes = params.moduleCaseTypes;
            self.allowUsercase = params.allowUsercase;

            self.setPropertiesMap = function (propertiesMap) {
                self.propertiesMap = ko.mapping.fromJS(propertiesMap);
            };
            self.setPropertiesMap(params.propertiesMap);

            self.setUsercasePropertiesMap = function (propertiesMap) {
                self.usercasePropertiesMap = ko.mapping.fromJS(propertiesMap);
            };
            self.setUsercasePropertiesMap(params.usercasePropertiesMap);

            self.descriptionDict = params.propertyDescriptions;

            self.saveButton = hqImport("hqwebapp/js/bootstrap3/main").initSaveButton({
                unsavedMessage: gettext("You have unchanged case settings"),
                save: function () {
                    var requires = self.caseConfigViewModel.actionType() === 'update' ? 'case' : 'none';
                    var subcases = _(self.caseConfigViewModel.subcases()).map(HQOpenSubCaseAction.from_case_transaction);
                    var actions = JSON.stringify(_(self.actions).extend(
                        HQFormActions.from_case_transaction(self.caseConfigViewModel.case_transaction), {
                            subcases: subcases,
                        }
                    ));

                    self.saveButton.ajax({
                        type: 'post',
                        url: self.save_url,
                        data: {
                            requires: requires,
                            actions: actions,
                        },
                        dataType: 'json',
                        success: function (data) {
                            var app_manager = hqImport('app_manager/js/app_manager');
                            app_manager.updateDOM(data.update);
                            self.requires(requires);
                            self.setPropertiesMap(data.propertiesMap);

                            if (_(data.propertiesMap).has(self.caseType)) {
                                hqImport('analytix/js/kissmetrix').track.event("Saved question as a Case Property", {
                                    questionsSaved: _.property(self.caseType)(data.propertiesMap).length,
                                });
                            }
                        },
                    });
                },
            });

            self.saveUsercaseButton = hqImport("hqwebapp/js/bootstrap3/main").initSaveButton({
                unsavedMessage: gettext("You have unchanged user properties settings"),
                save: function () {
                    var actions = JSON.stringify(_(self.actions).extend(
                        HQFormActions.from_usercase_transaction(self.caseConfigViewModel.usercase_transaction)
                    ));
                    self.saveUsercaseButton.ajax({
                        type: 'post',
                        url: self.save_url,
                        data: {
                            actions: actions,
                        },
                        dataType: 'json',
                        success: function (data) {
                            var app_manager = hqImport('app_manager/js/app_manager');
                            app_manager.updateDOM(data.update);
                            self.setUsercasePropertiesMap(data.setUsercasePropertiesMap);
                        },
                    });
                },
            });

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

            var questionScores = {};
            _(self.questions()).each(function (question, i) {
                questionScores[question.value] = i;
            });
            self.questionScores = questionScores;
            self.caseConfigViewModel = caseConfigViewModel(self);

            self.getQuestions = function (filter, excludeHidden, includeRepeat, excludeTrigger) {
                return caseConfigUtils.getQuestions(self.questions(), filter, excludeHidden, includeRepeat, excludeTrigger);
            };

            self.getAnswers = function (condition) {
                return caseConfigUtils.getAnswers(self.questions(), condition);
            };

            self.change = function () {
                self.saveButton.fire('change');
                self.forceRefreshTextchangeBinding(self.home);
            };

            self.usercaseChange = function () {
                self.saveUsercaseButton.fire('change');
                self.forceRefreshTextchangeBinding($('#usercase-config-ko'));
            };

            self.forceRefreshTextchangeBinding = function (domNode) {
                // This is a hack that I do not understand,
                // and really shouldn't be necessary.
                // For some reason, $home.on('textchange', 'input', blah)
                // loses track of the input element __answer__ in
                // "Only if the answer to __question__ is __answer__".
                // Flicking that input's textchange binding seems to
                // jigger that relationship back into place. #weird
                // (this is potentially expensive just because it's O(N)
                // but I'd be surprised if other things weren't too)
                var x = function () {};
                domNode.find('input')
                    .off('textchange', x)
                    .on('textchange', x);
            };

            self.init = function () {
                var $home = self.home;
                var $usercaseMgmt = $('#usercase-config-ko');
                _.delay(function () {
                    if ($home.length) {
                        $home.koApplyBindings(self);
                        $home.on('textchange', 'input', self.change)
                            // all select2's are represented by an input[type="hidden"]
                            .on('change', 'select, input[type="hidden"]', self.change)
                            .on('click', 'a', self.change);
                        self.forceRefreshTextchangeBinding($home);
                    }

                    if ($usercaseMgmt.length) {
                        $usercaseMgmt.koApplyBindings(self);
                        if (self.allowUsercase) {
                            $usercaseMgmt.on('textchange', 'input', self.usercaseChange)
                                .on('change', 'select, input[type="hidden"]', self.usercaseChange)
                                .on('click', 'a', self.usercaseChange);
                        } else {
                            $usercaseMgmt.find('input').prop('disabled', true);
                            $usercaseMgmt.find('select').prop('disabled', true);
                            $usercaseMgmt.find('a').off('click');
                            // Remove "Load properties" / "Save properties" link
                            _.each($usercaseMgmt.find('.add-property'), function (elem) {
                                elem.remove();
                            });
                        }
                        self.forceRefreshTextchangeBinding($usercaseMgmt);
                    }

                    caseConfigUtils.initRefreshQuestions(self.questions);
                });

            };

            return self;
        };


        var caseConfigViewModel = function (caseConfig) {
            var self = {};

            self.hasPrivilege = true;
            self.caseConfig = caseConfig;
            self.moduleCaseTypes = caseConfig.moduleCaseTypes;
            self.caseTypes = _.unique(_(self.moduleCaseTypes).map(function (moduleCaseType) {
                return moduleCaseType.case_type;
            }));
            self.getCaseTypeLabel = function (caseType) {
                var module_names = [],
                    label;
                for (var i = 0; i < self.moduleCaseTypes.length; i++) {
                    if (self.moduleCaseTypes[i].case_type === caseType) {
                        module_names.push(self.moduleCaseTypes[i].module_name);
                    }
                }
                label = module_names.join(', ');
                if (caseType === self.caseConfig.caseType) {
                    label = '*' + label;
                }
                return label + ' (' + caseType + ')';
            };
            self.case_transaction = HQFormActions.to_case_transaction(caseConfig.actions, caseConfig);
            self.usercase_transaction = HQFormActions.to_usercase_transaction(caseConfig.actions, caseConfig);
            self.subcases = ko.observableArray(
                _(caseConfig.actions.subcases).map(function (subcase) {
                    return HQOpenSubCaseAction.to_case_transaction(subcase, caseConfig);
                })
            );
            self.addSubCase = function () {
                if (!privileges.subcases) return;
                self.subcases.push(HQOpenSubCaseAction.to_case_transaction({}, caseConfig));
            };
            self.removeSubCase = function (subcase) {
                if (!privileges.subcases) return;
                self.subcases.remove(subcase);
            };

            self.actionType = ko.observable((function () {
                var opens_case = self.case_transaction.condition.type() !== 'never';
                var requires_case = self.caseConfig.requires() === 'case';
                var has_subcases = self.subcases().length;
                if (requires_case) {
                    return 'update';
                } else if (opens_case) {
                    return 'open';
                }
                return 'update';
            }()));

            self.showLeadRegistration = ko.computed(function () {
                return self.actionType() === 'open';
            });
            self.showLeadFollowup = ko.computed(function () {
                return self.actionType() === 'update';
            });

            self.actionType.subscribe(function (value) {
                var required;
                if (value === 'open') {
                    required = ['name'];
                    if (self.case_transaction.condition.type() === 'never') {
                        self.case_transaction.condition.type('always');
                    }
                } else {
                    required = [];
                }
                self.case_transaction.setRequired(required);
            });

            return self;
        };


        var baseMapping = function (model, include) {
            return {
                include: include,
                case_properties: {
                    create: function (options) {
                        return caseProperty.wrap(options.data, model);
                    },
                },
            };
        };
        var caseTransactionMapping = function (model) {
            return baseMapping(model, [
                'case_type', 'reference_id', 'condition', 'case_properties', 'case_preload', 'close_condition', 'allow',
            ]);
        };
        var usercaseTransactionMapping = function (model) {
            return baseMapping(model, ['case_properties', 'case_preload']);
        };

        var baseTransaction = function (mapping, saveButton, analyticsAction, data, caseConfig, hasPrivilege) {
            var self = {};
            ko.mapping.fromJS(data, mapping(self), self);

            self.hasPrivilege = hasPrivilege;
            self.caseConfig = caseConfig;
            self.saveOnlyEditedFormFieldsEnabled = toggles.toggleEnabled("SAVE_ONLY_EDITED_FORM_FIELDS");

            // link self.case_name to corresponding path observable in case_properties for convenience
            try {
                self.case_name = _(self.case_properties()).find(function (p) {
                    return p.key() === 'name' && p.required();
                }).path;
            } catch (e) {
                self.case_name = null;
            }

            self.sortProperties = function (p1, p2) {
                var validPaths = _.pluck(caseConfig.questions(), 'value');

                if (validPaths.includes(p1.path()) && validPaths.includes(p2.path())) {
                    return 0;
                } else if (!validPaths.includes(p1.path())) {
                    return -1;
                } else {
                    return 1;
                }
            };

            // Pagination and search
            self.searchAndFilter = true;
            self.case_property_query = ko.observable('');
            self.filtered_case_properties = ko.computed(function () {
                var query = self.case_property_query() || '';
                var props = _.filter(self.case_properties(), function (item) {
                    return (item.path() || '').indexOf(query) !== -1 || (item.key() || '').indexOf(query) !== -1;
                });
                props.sort(self.sortProperties);
                return props;
            });
            self.visible_case_properties = ko.observableArray();
            self.pagination_reset_flag = ko.observable(false);
            self.goToPage = function (page) {
                page = page || 1;
                var props = self.filtered_case_properties();
                var skip = self.per_page() * (page - 1);
                props = props.slice(skip, skip + self.per_page());
                self.visible_case_properties(props);
            };
            // Don't allow changing per page; "Add Property" button is where the per page changer usually is
            self.per_page = ko.observable(10);
            self.total_case_properties = ko.computed(function () {
                return self.filtered_case_properties().length;
            });
            self.goToPage(1);

            self.suggestedSaveProperties = ko.computed(function () {
                return caseConfigUtils.filteredSuggestedProperties(self.suggestedProperties(), self.case_properties());
            }, self);

            self.addProperty = function () {
                if (!self.hasPrivilege) return;
                var property = caseProperty.wrap({
                    path: '',
                    key: '',
                    required: false,
                    save_only_if_edited: false,
                }, self);

                self.case_properties.push(property);
                self.visible_case_properties.push(property);
                hqImport('analytix/js/google').track.event('Case Management', analyticsAction, 'Save Properties');
            };

            self.removeProperty = function (property) {
                if (!self.hasPrivilege) return;
                hqImport('analytix/js/google').track.event('Case Management', analyticsAction, 'Save Properties (remove)');
                self.case_properties.remove(property);
                self.visible_case_properties.remove(property);
                if (!self.visible_case_properties().length) {
                    self.pagination_reset_flag(!self.pagination_reset_flag());
                }
                saveButton.fire('change');
            };

            self.switchSaveOnlyIfEdited = function (property, event) {
                if (!self.hasPrivilege) return;
                var checked = event.target.checked;
                if (checked) {
                    hqImport('analytix/js/google').track.event('Case Management', analyticsAction, 'Checked "Save only if edited"');
                } else {
                    hqImport('analytix/js/google').track.event('Case Management', analyticsAction, 'Unchecked "Save only if edited"');
                }
                var updatedCaseProp = caseProperty.wrap(_.extend(ko.mapping.toJS(property), {save_only_if_edited: checked}), self);
                self.case_properties.replace(property, updatedCaseProp);
                self.visible_case_properties.replace(property, updatedCaseProp);
                saveButton.fire('change');
            };

            self.propertyCounts = ko.computed(function () {
                var count = {};
                _(self.case_properties()).each(function (p) {
                    var key = p.key();
                    if (!count.hasOwnProperty(key)) {
                        count[key] = 0;
                    }
                    return count[key] += 1;
                });
                return count;
            });

            self.repeat_context = function () {
                if (self.case_name) {
                    return caseConfig.get_repeat_context(self.case_name());
                } else {
                    return null;
                }
            };

            self.setRequired = function (required) {
                var delete_me = [];
                _(self.case_properties()).each(function (case_property) {
                    var key = case_property.key();
                    if (_(required).contains(key)) {
                        case_property.required(true);
                        required.splice(required.indexOf(key), 1);
                    } else {
                        if (case_property.required()) {
                            case_property.required(false);
                            if (!case_property.path()) {
                                delete_me.push(case_property);
                            }
                        }

                    }
                });
                _(delete_me).each(function (case_property) {
                    self.case_properties.remove(case_property);
                });
                _(required).each(function (key) {
                    self.case_properties.splice(0, 0, caseProperty.wrap({
                        path: '',
                        key: key,
                        required: true,
                    }, self));
                });
                self.pagination_reset_flag(!self.pagination_reset_flag());
            };

            self.unwrap = function () {
                ko.mapping.toJS(self, mapping(self));
            };

            return self;
        };

        var caseTransaction = function (data, caseConfig, hasPrivilege) {
            var self = baseTransaction(caseTransactionMapping, caseConfig.saveButton, 'Form Level', data, caseConfig, hasPrivilege);

            self.case_type(self.case_type() || caseConfig.caseType);

            self.close_case = ko.computed({
                read: function () {
                    if (self.close_condition) {
                        return self.close_condition.type() !== 'never';
                    } else {
                        return false;
                    }

                },
                write: function (value) {
                    self.close_condition.type(value ? 'always' : 'never');
                    self.caseConfig.saveButton.fire('change');
                },
            });

            return self;
        };


        var usercaseTransaction = function (data, caseConfig) {
            var self = baseTransaction(usercaseTransactionMapping, caseConfig.saveUsercaseButton, 'User Case Management', data, caseConfig, true);

            self.case_type = function () {
                return 'commcare-user';
            };

            return self;
        };


        var casePropertyBase = {
            mapping: {
                include: ['key', 'path', 'required', 'save_only_if_edited'],
            },
            wrap: function (data, case_transaction) {
                var self = ko.mapping.fromJS(data, caseProperty.mapping);
                self.case_transaction = case_transaction;
                self.caseType = ko.computed(function () {
                    return self.case_transaction.case_type();
                });
                self.updatedDescription = ko.observable();
                self.description = ko.computed({
                    read: function () {
                        if (self.updatedDescription() !== undefined) {
                            return self.updatedDescription();
                        }
                        var config = self.case_transaction.caseConfig;
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
            wrap: function (data, case_transaction) {
                var self = casePropertyBase.wrap(data, case_transaction);
                self.defaultKey = ko.computed(function () {
                    var path = self.path() || '';
                    var value = path.split('/');
                    value = value[value.length - 1];
                    return value;
                });
                self.repeat_context = function () {
                    return case_transaction.caseConfig.get_repeat_context(self.path());
                };
                self.validate = ko.computed(function () {
                    if (self.path() || self.key()) {
                        if (case_transaction.propertyCounts()[self.key()] > 1) {
                            return gettext("Property updated by two questions");
                        } else if (case_transaction.caseConfig.reserved_words.indexOf(self.key()) !== -1) {
                            return '<strong>' + self.key() + '</strong> is a reserved word';
                        } else if (self.repeat_context() && self.repeat_context() !== case_transaction.repeat_context()) {
                            return gettext('Inside the wrong repeat!');
                        } else if (_.difference(
                            _.initial(self.key().split(/\//)),
                            case_transaction.caseConfig.valid_index_names
                        ).length) {
                            return gettext('Property uses unrecognized prefix <strong>' +
                                self.key().replace(/\/[^\/]*$/, '') + '</strong>');
                        }
                    }
                    return null;
                });
                return self;
            },
        };

        var DEFAULT_CONDITION_ALWAYS = {
            type: 'always',
            question: null,
            answer: null,
            operator: null,
        };

        var DEFAULT_CONDITION_NEVER = {
            type: 'never',
            question: null,
            answer: null,
            operator: null,
        };

        // Default UpdateCaseAction json
        var DEFAULT_UPDATE_ALWAYS = {
            question_path: '',
            update_mode: 'always',
        };

        var cleanCondition = function (condition) {
            if (condition.type !== 'if') {
                condition.question = null;
                condition.answer = null;
                condition.operator = null;
            }
            return condition;
        };

        var HQFormActions = {
            normalize: function (o) {
                var self = {};
                self.open_case = {
                    condition: (o.open_case || {}).condition || DEFAULT_CONDITION_ALWAYS,
                    name_update: (o.open_case || {}).name_update || DEFAULT_UPDATE_ALWAYS,
                };
                self.update_case = {
                    update: (o.update_case || {}).update || {},
                };
                self.case_preload = {
                    preload: (o.case_preload || {}).preload || {},
                };
                self.close_case = {
                    condition: (o.close_case || {}).condition || DEFAULT_CONDITION_ALWAYS,
                };
                self.usercase_update = {
                    update: (o.usercase_update || {}).update || {},
                };
                self.usercase_preload = {
                    preload: (o.usercase_preload || {}).preload || {},
                };
                return self;
            },
            to_case_transaction: function (o, caseConfig) {
                var self = HQFormActions.normalize(o);
                var required_properties = (caseConfig.requires() === 'none' &&
                    caseConfig.actions.open_case.condition.type !== "never" &&
                    !o.update_case.update.name) ? [{
                        key: 'name',
                        path: self.open_case.name_update.question_path,
                        required: true,
                        save_only_if_edited: self.open_case.name_update.update_mode === 'edit',
                    }] : [];
                var case_properties = caseConfigUtils.propertyDictToArray(
                    required_properties,
                    self.update_case.update,
                    caseConfig
                );
                var case_preload = caseConfigUtils.preloadDictToArray(
                    self.case_preload.preload,
                    caseConfig
                );
                var x = caseTransaction({
                    case_type: null, // will get overridden by the default
                    reference_id: null, // not used in normal case config
                    case_properties: case_properties,
                    case_preload: case_preload,
                    condition: self.open_case.condition,
                    close_condition: self.close_case.condition,
                    suggestedProperties: function () {
                        if (_(caseConfig.propertiesMap).has(this.case_type())) {
                            return caseConfig.propertiesMap[this.case_type()]();
                        } else {
                            return [];
                        }
                    },
                }, caseConfig, true);
                _.delay(function () {
                    x.allow = {
                        condition: ko.computed(function () {
                            return caseConfig.caseConfigViewModel.actionType() === 'open';
                        }),
                        repeats: function () {
                            return false;
                        },
                    };
                });
                return x;
            },
            from_case_transaction: function (case_transaction) {
                var o = ko.mapping.toJS(case_transaction, caseTransactionMapping(case_transaction));
                var x = caseConfigUtils.propertyArrayToDict(['name'], o.case_properties);
                var case_properties = x[0],
                    open_name_update = x[1].name;
                var case_preload = caseConfigUtils.preloadArrayToDict(o.case_preload);
                var open_condition = o.condition;
                var close_condition = o.close_condition;
                var update_condition = DEFAULT_CONDITION_ALWAYS;
                var actionType = case_transaction.caseConfig.caseConfigViewModel.actionType();

                if (actionType === 'open') {
                    if (open_condition.type === 'never') {
                        open_condition.type = 'always';
                    }
                } else {
                    open_condition.type = 'never';

                }

                update_condition.type = 'always';

                return {
                    open_case: {
                        condition: cleanCondition(open_condition),
                        name_update: open_name_update,
                    },
                    update_case: {
                        update: case_properties,
                        condition: cleanCondition(update_condition),
                    },
                    case_preload: {
                        preload: case_preload,
                        condition: cleanCondition(update_condition),
                    },
                    close_case: {
                        condition: cleanCondition(close_condition),
                    },
                };
            },
            to_usercase_transaction: function (o, caseConfig) {
                var self = HQFormActions.normalize(o);
                var case_properties = caseConfigUtils.propertyDictToArray(
                    [], // usercase has no required properties; it has already been created with everything it needs
                    self.usercase_update.update,
                    caseConfig
                );
                var case_preload = caseConfigUtils.preloadDictToArray(
                    self.usercase_preload.preload,
                    caseConfig
                );
                return usercaseTransaction({
                    case_properties: case_properties,
                    case_preload: case_preload,
                    allow: {
                        repeats: function () {
                            // This placeholder function allows us to reuse the "case-config:case-properties:question"
                            // template in case_config_ko_templates.html
                            return true;
                        },
                    },

                    suggestedProperties: function () {
                        if (_(caseConfig.usercasePropertiesMap).has('commcare-user')) {
                            return caseConfig.usercasePropertiesMap['commcare-user']();
                        } else {
                            return [];
                        }
                    },
                }, caseConfig);
            },
            from_usercase_transaction: function (usercase_transaction) {
                var o = ko.mapping.toJS(usercase_transaction, usercaseTransactionMapping(usercase_transaction));
                var x = caseConfigUtils.propertyArrayToDict([], o.case_properties);
                var case_properties = x[0];
                var case_preload = caseConfigUtils.preloadArrayToDict(o.case_preload);
                return {
                    usercase_update: {
                        update: case_properties,
                        condition: cleanCondition(DEFAULT_CONDITION_ALWAYS), // usercase_update action is always active
                    },
                    usercase_preload: {
                        preload: case_preload,
                    },
                };
            },
        };

        var HQOpenSubCaseAction = {
            normalize: function (o) {
                var self = {};
                self.case_type = o.case_type || null;
                self.name_update = o.name_update || {};
                self.reference_id = o.reference_id || null;
                self.case_properties = o.case_properties || {};
                self.condition = o.condition || DEFAULT_CONDITION_ALWAYS;
                self.close_condition = o.close_condition || DEFAULT_CONDITION_NEVER;
                self.repeat_context = o.repeat_context;
                self.relationship = o.relationship || null;
                return self;
            },
            to_case_transaction: function (o, caseConfig) {
                var self = HQOpenSubCaseAction.normalize(o);
                var case_properties = caseConfigUtils.propertyDictToArray([{
                    path: self.name_update.question_path,
                    key: 'name',
                    required: true,
                    save_only_if_edited: o.name_update ?
                        o.name_update.update_mode === 'edit' : false,
                }], self.case_properties, caseConfig);

                return caseTransaction({
                    case_type: self.case_type,
                    reference_id: self.reference_id,
                    case_properties: case_properties,
                    condition: self.condition,
                    close_condition: self.close_condition,
                    relationship: self.relationship,
                    suggestedProperties: function () {
                        if (this.case_type() && _(caseConfig.propertiesMap).has(this.case_type())) {
                            var all = caseConfig.propertiesMap[this.case_type()]();
                            return _(all).filter(function (property) {
                                return !_(property).contains('/');
                            });
                        } else {
                            return [];
                        }
                    },
                    allow: {
                        condition: function () {
                            return true;
                        },
                        case_preload: function () {
                            return false;
                        },
                        repeats: function () {
                            return true;
                        },
                        parentProperties: function () {
                            return false;
                        },
                    },
                }, caseConfig, privileges.subcases);
            },
            from_case_transaction: function (case_transaction) {
                var o = ko.mapping.toJS(case_transaction, caseTransactionMapping(case_transaction));
                var x = caseConfigUtils.propertyArrayToDict(['name'], o.case_properties);
                var case_properties = x[0],
                    open_subcase_update_name = x[1].name;

                return {
                    name_update: open_subcase_update_name,
                    case_type: o.case_type,
                    case_properties: case_properties,
                    reference_id: o.reference_id,
                    condition: cleanCondition(o.condition),
                    close_condition: cleanCondition(o.close_condition),
                    repeat_context: case_transaction.repeat_context(),
                };
            },
        };

        if (initial_page_data('has_form_source')) {
            var caseConfig = caseConfig(_.extend({}, initial_page_data("case_config_options"), {
                home: $('#case-config-ko'),
                requires: ko.observable(initial_page_data("form_requires")),
            }));
            caseConfig.init();
        }
    });
});

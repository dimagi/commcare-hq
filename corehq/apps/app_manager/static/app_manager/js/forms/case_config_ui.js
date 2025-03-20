hqDefine("app_manager/js/forms/case_config_ui", [
    "jquery",
    "knockout",
    "underscore",
    "app_manager/js/case_config_utils",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/privileges",
    "hqwebapp/js/toggles",
    "hqwebapp/js/bootstrap3/main",
    "app_manager/js/app_manager",
    "analytix/js/kissmetrix",
    "analytix/js/google",
], function (
    $,
    ko,
    _,
    caseConfigUtils,
    initialPageData,
    privileges,
    toggles,
    main,
    appManager,
    kissmetrix,
    google,
) {
    $(function () {
        if (initialPageData.get('module_doc_type') === "AdvancedModule") {
            return;
        };

        const addOnsPrivileges = initialPageData.get('add_ons_privileges');
        var actionNames = ["open_case", "update_case", "close_case", "case_preload",
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
                _(actionNames).each(function (actionName) {
                    actions[actionName] = a[actionName];
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

            self.trackGoogleEvent = function () {
                google.track.event(...arguments);
            };

            self.setPropertiesMap = function (propertiesMap) {
                self.propertiesMap = ko.mapping.fromJS(propertiesMap);
            };
            self.setPropertiesMap(params.propertiesMap);

            self.setUsercasePropertiesMap = function (propertiesMap) {
                self.usercasePropertiesMap = ko.mapping.fromJS(propertiesMap);
            };
            self.setUsercasePropertiesMap(params.usercasePropertiesMap);

            self.descriptionDict = params.propertyDescriptions;
            self.deprecatedPropertiesDict = params.deprecatedProperties;

            self.saveButton = main.initSaveButton({
                unsavedMessage: gettext("You have unchanged case settings"),
                save: function () {
                    var requires = self.caseConfigViewModel.actionType() === 'update' ? 'case' : 'none';
                    var subcases = _(self.caseConfigViewModel.subcases()).map(HQOpenSubCaseAction.from_case_transaction);
                    var actions = JSON.stringify(_(self.actions).extend(
                        HQFormActions.from_case_transaction(self.caseConfigViewModel.case_transaction), {
                            subcases: subcases,
                        },
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
                            appManager.updateDOM(data.update);
                            self.requires(requires);
                            self.setPropertiesMap(data.propertiesMap);

                            if (_(data.propertiesMap).has(self.caseType)) {
                                kissmetrix.track.event("Saved question as a Case Property", {
                                    questionsSaved: _.property(self.caseType)(data.propertiesMap).length,
                                });
                            }
                        },
                    });
                },
            });

            self.saveUsercaseButton = main.initSaveButton({
                unsavedMessage: gettext("You have unchanged user properties settings"),
                save: function () {
                    var actions = JSON.stringify(_(self.actions).extend(
                        HQFormActions.from_usercase_transaction(self.caseConfigViewModel.usercase_transaction),
                    ));
                    self.saveUsercaseButton.ajax({
                        type: 'post',
                        url: self.save_url,
                        data: {
                            actions: actions,
                        },
                        dataType: 'json',
                        success: function (data) {
                            appManager.updateDOM(data.update);
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
                            // help links should not trigger a change.
                            // I did not see anchor tags that *should* trigger a change, but left in this trigger.
                            // Ideally, changes should be triggered off something more specific than an anchor tag
                            .on('click', ':not(.hq-help) > a', self.change);
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
                var moduleNames = [],
                    label;
                for (var i = 0; i < self.moduleCaseTypes.length; i++) {
                    if (self.moduleCaseTypes[i].case_type === caseType) {
                        moduleNames.push(self.moduleCaseTypes[i].module_name);
                    }
                }
                label = moduleNames.join(', ');
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
                }),
            );
            self.addSubCase = function () {
                if (!addOnsPrivileges.subcases) {
                    return;
                }
                self.subcases.push(HQOpenSubCaseAction.to_case_transaction({}, caseConfig));
            };
            self.removeSubCase = function (subcase) {
                if (!addOnsPrivileges.subcases) {
                    return;
                }
                self.subcases.remove(subcase);
            };

            self.actionType = ko.observable((function () {
                var opensCase = self.case_transaction.condition.type() !== 'never';
                var requiresCase = self.caseConfig.requires() === 'case';
                if (requiresCase) {
                    return 'update';
                } else if (opensCase) {
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
                if (!self.hasPrivilege) {
                    return;
                }
                var property = caseProperty.wrap({
                    path: '',
                    key: '',
                    required: false,
                    save_only_if_edited: false,
                }, self);

                self.case_properties.push(property);
                self.visible_case_properties.push(property);
                google.track.event('Case Management', analyticsAction, 'Save Properties');
            };

            self.removeProperty = function (property) {
                if (!self.hasPrivilege) {
                    return;
                }
                google.track.event('Case Management', analyticsAction, 'Save Properties (remove)');
                self.case_properties.remove(property);
                self.visible_case_properties.remove(property);
                if (!self.visible_case_properties().length) {
                    self.pagination_reset_flag(!self.pagination_reset_flag());
                }
                saveButton.fire('change');
            };

            self.switchSaveOnlyIfEdited = function (property, event) {
                if (!self.hasPrivilege) {
                    return;
                }
                var checked = event.target.checked;
                if (checked) {
                    google.track.event('Case Management', analyticsAction, 'Checked "Save only if edited"');
                } else {
                    google.track.event('Case Management', analyticsAction, 'Unchecked "Save only if edited"');
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
                    if (!_.has(count, key)) {
                        count[key] = 0;
                    }
                    return count[key] += 1;
                });
                return count;
            });

            self.hasDeprecatedProperties = ko.computed(function () {
                if (privileges.hasPrivilege('data_dictionary')) {
                    for (const p of self.case_properties()) {
                        if (p.isDeprecated()) {
                            return true;
                        }
                    }
                }
                return false;
            });

            self.repeat_context = function () {
                if (self.case_name) {
                    return caseConfig.get_repeat_context(self.case_name());
                } else {
                    return null;
                }
            };

            self.setRequired = function (required) {
                var deleteMe = [];
                _(self.case_properties()).each(function (caseProperty) {
                    var key = caseProperty.key();
                    if (_(required).contains(key)) {
                        caseProperty.required(true);
                        required.splice(required.indexOf(key), 1);
                    } else {
                        if (caseProperty.required()) {
                            caseProperty.required(false);
                            if (!caseProperty.path()) {
                                deleteMe.push(caseProperty);
                            }
                        }

                    }
                });
                _(deleteMe).each(function (caseProperty) {
                    self.case_properties.remove(caseProperty);
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
            data.title = gettext("Save Questions to Case Properties");
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
            data.title = gettext("Save Questions to User Properties");
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
            wrap: function (data, caseTransaction) {
                var self = ko.mapping.fromJS(data, caseProperty.mapping);
                self.case_transaction = caseTransaction;
                self.caseType = ko.computed(function () {
                    return self.case_transaction.case_type();
                });
                self.updatedDescription = ko.observable();
                self.isDeprecated = ko.computed(function () {
                    if (privileges.hasPrivilege('data_dictionary')) {
                        const config = self.case_transaction.caseConfig;
                        const depProps = config.deprecatedPropertiesDict[self.caseType()];
                        if (depProps && self.key() !== 'name') {
                            return depProps.includes(self.key());
                        }
                    }
                    return false;
                });
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
            wrap: function (data, caseTransaction) {
                var self = casePropertyBase.wrap(data, caseTransaction);
                self.defaultKey = ko.computed(function () {
                    var path = self.path() || '';
                    var value = path.split('/');
                    value = value[value.length - 1];
                    return value;
                });
                self.repeat_context = function () {
                    return caseTransaction.caseConfig.get_repeat_context(self.path());
                };
                self.validate = ko.computed(function () {
                    if (self.path() || self.key()) {
                        if (caseTransaction.propertyCounts()[self.key()] > 1) {
                            return gettext("Property updated by two questions");
                        } else if (caseTransaction.caseConfig.reserved_words.indexOf(self.key()) !== -1) {
                            return '<strong>' + self.key() + '</strong> is a reserved word';
                        } else if (self.repeat_context() && self.repeat_context() !== caseTransaction.repeat_context()) {
                            return gettext('Inside the wrong repeat!');
                        } else if (_.difference(
                            _.initial(self.key().split(/\//)),
                            caseTransaction.caseConfig.valid_index_names,
                        ).length) {
                            return gettext('Property uses unrecognized prefix <strong>' +
                                self.key().replace(/\/[^/]*$/, '') + '</strong>');
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
                var requiredProperties = (caseConfig.requires() === 'none' &&
                    caseConfig.actions.open_case.condition.type !== "never" &&
                    !o.update_case.update.name) ? [{
                        key: 'name',
                        path: self.open_case.name_update.question_path,
                        required: true,
                        save_only_if_edited: self.open_case.name_update.update_mode === 'edit',
                    }] : [];
                var caseProperties = caseConfigUtils.propertyDictToArray(
                    requiredProperties,
                    self.update_case.update,
                    caseConfig,
                );
                var casePreload = caseConfigUtils.preloadDictToArray(
                    self.case_preload.preload,
                    caseConfig,
                );
                var x = caseTransaction({
                    case_type: null, // will get overridden by the default
                    reference_id: null, // not used in normal case config
                    case_properties: caseProperties,
                    case_preload: casePreload,
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
            from_case_transaction: function (caseTransaction) {
                var o = ko.mapping.toJS(caseTransaction, caseTransactionMapping(caseTransaction));
                var x = caseConfigUtils.propertyArrayToDict(['name'], o.case_properties);
                var caseProperties = x[0],
                    openNameUpdate = x[1].name;
                var casePreload = caseConfigUtils.preloadArrayToDict(o.case_preload);
                var openCondition = o.condition;
                var closeCondition = o.close_condition;
                var updateCondition = DEFAULT_CONDITION_ALWAYS;
                var actionType = caseTransaction.caseConfig.caseConfigViewModel.actionType();

                if (actionType === 'open') {
                    if (openCondition.type === 'never') {
                        openCondition.type = 'always';
                    }
                } else {
                    openCondition.type = 'never';

                }

                updateCondition.type = 'always';

                return {
                    open_case: {
                        condition: cleanCondition(openCondition),
                        name_update: openNameUpdate,
                    },
                    update_case: {
                        update: caseProperties,
                        condition: cleanCondition(updateCondition),
                    },
                    case_preload: {
                        preload: casePreload,
                        condition: cleanCondition(updateCondition),
                    },
                    close_case: {
                        condition: cleanCondition(closeCondition),
                    },
                };
            },
            to_usercase_transaction: function (o, caseConfig) {
                var self = HQFormActions.normalize(o);
                var caseProperties = caseConfigUtils.propertyDictToArray(
                    [], // usercase has no required properties; it has already been created with everything it needs
                    self.usercase_update.update,
                    caseConfig,
                );
                var casePreload = caseConfigUtils.preloadDictToArray(
                    self.usercase_preload.preload,
                    caseConfig,
                );
                return usercaseTransaction({
                    case_properties: caseProperties,
                    case_preload: casePreload,
                    case_type: 'commcare-user', // will get overridden by the default. Set here to check deprecated status for saved properties on initial page load
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
            from_usercase_transaction: function (usercaseTransaction) {
                var o = ko.mapping.toJS(usercaseTransaction, usercaseTransactionMapping(usercaseTransaction));
                var x = caseConfigUtils.propertyArrayToDict([], o.case_properties);
                var caseProperties = x[0];
                var casePreload = caseConfigUtils.preloadArrayToDict(o.case_preload);
                return {
                    usercase_update: {
                        update: caseProperties,
                        condition: cleanCondition(DEFAULT_CONDITION_ALWAYS), // usercase_update action is always active
                    },
                    usercase_preload: {
                        preload: casePreload,
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
                var caseProperties = caseConfigUtils.propertyDictToArray([{
                    path: self.name_update.question_path,
                    key: 'name',
                    required: true,
                    save_only_if_edited: o.name_update ?
                        o.name_update.update_mode === 'edit' : false,
                }], self.case_properties, caseConfig);

                return caseTransaction({
                    case_type: self.case_type,
                    reference_id: self.reference_id,
                    case_properties: caseProperties,
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
                }, caseConfig, addOnsPrivileges.subcases);
            },
            from_case_transaction: function (caseTransaction) {
                var o = ko.mapping.toJS(caseTransaction, caseTransactionMapping(caseTransaction));
                var x = caseConfigUtils.propertyArrayToDict(['name'], o.case_properties);
                var caseProperties = x[0],
                    openSubcaseUpdateName = x[1].name;

                return {
                    name_update: openSubcaseUpdateName,
                    case_type: o.case_type,
                    case_properties: caseProperties,
                    reference_id: o.reference_id,
                    condition: cleanCondition(o.condition),
                    close_condition: cleanCondition(o.close_condition),
                    repeat_context: caseTransaction.repeat_context(),
                };
            },
        };

        if (initialPageData.get('has_form_source')) {
            var caseConfigObj = caseConfig(_.extend({}, initialPageData.get("case_config_options"), {
                home: $('#case-config-ko'),
                requires: ko.observable(initialPageData.get("form_requires")),
            }));
            caseConfigObj.init();
        }
    });
});

hqDefine('app_manager/js/forms/advanced/actions', function () {
    var caseConfigUtils = hqImport('app_manager/js/case_config_utils'),
        caseProperty = hqImport('app_manager/js/forms/advanced/case_properties').caseProperty,
        casePreloadProperty = hqImport('app_manager/js/forms/advanced/case_properties').casePreloadProperty,
        toggles = hqImport("hqwebapp/js/toggles");

    var caseIndex = {
        mapping: {
            include: ['tag', 'reference_id', 'relationship', 'relationship_question'],
        },
        wrap: function (data) {
            var self = ko.mapping.fromJS(data, caseIndex.mapping);
            self.relationship.subscribe(function (value) {
                if (value === 'extension' && self.reference_id() !== 'host') {
                    self.reference_id('host');
                } else if (value === 'child' && self.reference_id() !== 'parent') {
                    self.reference_id('parent');
                } else if (value === 'question') {
                    self.reference_id('');
                }
            });

            return self;
        },
    };

    var actionBase = {
        validate: function (self, caseType, caseTag) {
            if (!self.caseConfig.caseConfigViewModel) {
                return;
            }
            if (!caseType) {
                return gettext("Case Type required");
            } else if (!caseTag || (self.warn_blank_case_tag() && !toggles.toggleEnabled('ALLOW_BLANK_CASE_TAGS'))) {
                return gettext("Case Tag required");
            }
            if (!/^[a-zA-Z][\w_-]*(\/[a-zA-Z][\w_-]*)*$/.test(caseTag)) {
                return gettext("Case Tag: only letters, numbers, '-', and '_' allowed");
            }
            var tags = self.caseConfig.caseConfigViewModel.getCaseTags('all');
            if (_.where(tags, { value: caseTag }).length > 1) {
                return gettext("Case Tag already in use");
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
                    self.caseConfig.saveButton.fire('change');
                },
            };
        },
        case_tag: function (self) {
            self.case_tag.extend({
                withPrevious: 1,
            });

            self.case_tag.subscribe(function (tag) {
                if (!self.auto_select && !tag) {
                    // Don't allow user to blank out case tag
                    self.warn_blank_case_tag(true);
                    if (!toggles.toggleEnabled('ALLOW_BLANK_CASE_TAGS')) {
                        self.case_tag(self.case_tag.previous());
                    }
                    return;
                }
                if (self.case_tag.previous()) {
                    self.warn_blank_case_tag(false);
                }
                self.caseConfig.caseConfigViewModel.renameCaseTag(self.case_tag.previous(), tag, true);
            });

            return self.case_tag;
        },
        propertyCounts: function (self) {
            return function () {
                var count = {};
                _(self.case_properties()).each(function (p) {
                    var key = p.key();
                    if (!_.has(count, key)) {
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
            var nameSnip = "<i class=\"fa fa-tag\"></i> <%- action.case_tag() %> (<%- action.case_type() %>)";
            var closeSnip = "<% if (action.close_case()) { %> : close<% }%>";
            var spanSnip = '<span class="text-muted" style="font-weight: normal;">';
            if (action.actionType === 'open') {
                return _.template(
                    nameSnip + spanSnip +
                    '<% if (action.parent_tags()) { %> : ' +
                    gettext('subcase of') + '<span style="font-weight: bold;"><%- action.parent_tags() %></span>' +
                    '<% } %>' + closeSnip + "</span>")({
                    action: action,
                });
            } else {
                if (action.auto_select) {
                    nameSnip = "<i class=\"fa fa-tag\"></i> <%- action.case_tag() %> (" + gettext("autoselect mode: ") + "<%- action.auto_select.mode() %>)";
                }
                if (action.load_case_from_fixture) {
                    nameSnip += gettext(" (from fixture)");
                }
                return _.template(nameSnip + spanSnip +
                    "<% if (action.hasPreload()) { %> : load<% } %>" +
                    "<% if (action.hasCaseProperties()) { %> : update<% } %>" +
                    closeSnip + "</span>")({
                    action: action,
                });
            }
        },
        suggestedProperties: function (action, allowParent) {
            var properties = [];
            var propertiesMap = action.caseConfig.propertiesMap;
            var caseType = action.case_type();
            if (_(propertiesMap).has(caseType)) {
                properties = _.filter(propertiesMap[caseType](), function (p) {
                    return allowParent ? true : p.indexOf('/') === -1;
                });
            }
            return properties;
        },
        relationshipTypes: ['child', 'extension', 'question'],
    };

    var loadUpdateAction = {
        mapping: function (self) {
            return {
                include: [
                    'case_type',
                    'details_module',
                    'case_tag',
                    'close_condition',
                    'show_product_stock',
                    'product_program',
                ],
                preload: {
                    create: function (options) {
                        return casePreloadProperty.wrap(options.data, self);
                    },
                },
                case_properties: {
                    create: function (options) {
                        return caseProperty.wrap(options.data, self);
                    },
                },
                auto_select: {
                    create: function (options) {
                        if (options.data) {
                            return autoSelect.wrap(options.data, self);
                        } else {
                            return null;
                        }
                    },
                },
                load_case_from_fixture: {
                    create: function (options) {
                        if (options.data) {
                            return loadCaseFromFixture.wrap(options.data, self);
                        } else {
                            return null;
                        }
                    },
                },
                case_index: {
                    create: function (options) {
                        return caseIndex.wrap(options.data);
                    },
                },
            };
        },
        wrap: function (data, caseConfig) {
            var self = {
                caseConfig: caseConfig,
                actionType: 'load',
            };
            ko.mapping.fromJS(data, loadUpdateAction.mapping(self), self);
            self.hasPrivilege = true;

            // needed for compatibility with shared templates
            self.searchAndFilter = false;
            self.visible_case_properties = ko.computed(function () {
                return self.case_properties();
            });

            // for compatibility with common templates
            // template: case-config:condition
            self.allow = {
                repeats: function () {
                    return false;
                },
            };

            self.warn_blank_case_tag = ko.observable(false);

            self.available_modules = ko.computed(function () {
                return caseConfig.getModulesForCaseType(self.case_type(), self.show_product_stock());
            });

            if (self.auto_select) {
                self.auto_select.mode.subscribe(function (value) {
                    // suggestedProperties need to be those of case type "commcare-user"
                    if (value === 'usercase') {
                        self.case_type('commcare-user');
                    } else {
                        self.case_type(null);
                    }

                    _.defer(function () {
                        $('.hq-help-template').each(function () {
                            hqImport("hqwebapp/js/bootstrap3/main").transformHelpTemplate($(this), true);
                        });
                    });
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
                        self.caseConfig.caseConfigViewModel.renameCaseTag(self.case_tag(), newTag);
                    } else {
                        self.product_program('');
                    }
                },
            });

            self.subcase = ko.computed({
                read: function () {
                    return self.case_index.tag();
                },
                write: function (value) {
                    if (value) {
                        var index = self.caseConfig.caseConfigViewModel.load_update_cases.indexOf(self);
                        if (index > 0) {
                            var parent = self.caseConfig.caseConfigViewModel.load_update_cases()[index - 1];
                            self.case_index.tag(parent.case_tag());
                        }
                    } else {
                        self.case_index.tag('');
                    }
                },
            });

            self.case_tag = actionBase.case_tag(self);

            self.close_case = ko.computed(actionBase.close_case(self));

            self.validate = ko.computed(function () {
                if (self.auto_select) {
                    var mode = self.auto_select.mode();
                    var valueSource = self.auto_select.value_source();
                    var valueKey = self.auto_select.value_key();
                    if (!mode) {
                        return gettext("Autoselect mode required");
                    } else if (!valueKey && mode !== 'usercase') {
                        return gettext('Property required');
                    } else if (!valueSource) {
                        if (mode === 'case') {
                            return gettext('Case required');
                        } else if (mode === 'fixture') {
                            return gettext('Lookup table tag required');
                        }
                    }
                    if (!self.case_type()) {
                        return gettext('Expected case type required');
                    }
                    return null;
                } else {
                    return actionBase.validate(self, self.case_type(), self.case_tag());
                }
            });

            // for compatibility with common templates
            self.case_preload = ko.computed(function () {
                return self.preload();
            });

            self.propertyCounts = ko.computed(actionBase.propertyCounts(self));

            self.preloadCounts = ko.computed(function () {
                var count = {};
                _(self.preload()).each(function (p) {
                    var path = p.path();
                    if (!_.has(count, path)) {
                        count[path] = 0;
                    }
                    return count[path] += 1;
                });
                return count;
            });

            self.suggestedProperties = ko.computed(function () {
                return actionBase.suggestedProperties(self, !self.subcase());
            });

            self.addProperty = function () {
                self.case_properties.push(caseProperty.wrap({
                    key: '',
                    path: '',
                    required: false,
                }, self));
            };

            self.removeProperty = function (property) {
                self.case_properties.remove(property);
                self.caseConfig.saveButton.fire('change');
            };

            self.addPreload = function () {
                self.preload.push(casePreloadProperty.wrap({
                    key: '',
                    path: '',
                    required: false,
                }, self));
            };

            self.removePreload = function (property) {
                self.preload.remove(property);
                self.caseConfig.saveButton.fire('change');
            };

            self.hasPreload = function () {
                return _.find(self.preload(), function (prop) {
                    return !prop.isBlank();
                });
            };

            self.hasCaseProperties = function () {
                return _.find(self.case_properties(), function (prop) {
                    return !prop.isBlank();
                });
            };

            self.header = ko.computed(function () {
                return actionBase.header(self);
            });

            self.relationshipTypes = actionBase.relationshipTypes;

            var addCircular = function () {
                // hacky way to prevent trying to access caseConfigViewModel before it is defined
                self.allow_product_stock = ko.computed(function () {
                    var supported = self.caseConfig.case_supports_products(self.case_type());
                    var loadupdatecases = self.caseConfig.caseConfigViewModel.load_update_cases;
                    return supported && loadupdatecases.indexOf(self) === loadupdatecases().length - 1;
                });

                self.disable_tag = ko.computed(function () {
                    return self.show_product_stock() && self.allow_product_stock();
                });

                self.auto_select_modes = ko.computed(function () {
                    return caseConfig.getAutoSelectModes(self);
                });
                self.validate_subcase = ko.computed(function () {
                    if (!self.caseConfig.caseConfigViewModel) {
                        return;
                    }
                    if (!self.case_index.tag()) {
                        return null;
                    }
                    var parent = self.caseConfig.caseConfigViewModel.getActionFromTag(self.case_index.tag());
                    if (!parent) {
                        return gettext("Subcase parent reference is missing");
                    } else if (!self.case_index.reference_id()) {
                        return gettext('Parent reference ID required for subcases: ') + self.case_index.tag();
                    } else if (parent.actionType === 'open') {
                        if (!parent.repeat_context()) {
                            return null;
                        } else if (!self.repeat_context() ||
                            // manual string startsWith
                            self.repeat_context().lastIndexOf(parent.repeat_context(), 0) === 0) {
                            return gettext('Subcase must be in same repeat context as parent "') + self.case_index.tag() + '".';
                        }
                    }
                    return null;

                });

                self.moveable = ko.computed(function () {
                    // load / update case actions implicitly depend on the previously defined
                    // case when a subcase relationship is defined because of this implicit
                    // relationship, we do not support moving their position in the case management screen

                    if (!self.caseConfig.caseConfigViewModel) {
                        // The view model hasn't been initialized meaning there are no case actions defined
                        // If no case actions are defined, we can't have a parent reference
                        return true;
                    }
                    if (self.subcase()) {
                        // this action has the subcase of a previous case checked
                        return false;
                    }

                    var loadActions = self.caseConfig.caseConfigViewModel.load_update_cases(),
                        foundSelf = false,
                        nextAction = _.find(loadActions, function (action) {
                            if (foundSelf) {
                                return true;
                            }
                            if (action.case_tag() === self.case_tag()) {
                                foundSelf = true;
                            }
                        });

                    if (nextAction) {
                        // if the action following the action defined by self is using a subcase, it cannot be moved
                        return !nextAction.subcase();
                    }
                    return true;
                });
            };

            if (!self.caseConfig.caseConfigViewModel) {
                _.delay(addCircular);
            } else {
                addCircular();
            }

            // needed for compatibility with shared templates
            self.searchAndFilter = false;
            self.visible_case_properties = ko.computed(function () {
                return self.case_properties();
            });
            self.saveOnlyEditedFormFieldsEnabled = toggles.toggleEnabled("SAVE_ONLY_EDITED_FORM_FIELDS");

            return self;
        },
        unwrap: function (self) {
            var blank = function (prop) {
                return prop.isBlank();
            };
            self.preload.remove(blank);
            self.case_properties.remove(blank);
            actionBase.clean_condition(self.close_condition);
            self.show_product_stock(self.disable_tag());
            var action = ko.mapping.toJS(self, loadUpdateAction.mapping(self));

            action.preload = caseConfigUtils.preloadArrayToDict(action.preload);
            action.case_properties = caseConfigUtils.propertyArrayToDict([], action.case_properties)[0];
            return action;
        },
    };

    var openCaseAction = {
        mapping: function (self) {
            return {
                include: [
                    'case_type',
                    'name_update',
                    'case_tag',
                    'open_condition',
                    'close_condition',
                ],
                case_properties: {
                    create: function (options) {
                        return caseProperty.wrap(options.data, self);
                    },
                },
                case_indices: {
                    create: function (options) {
                        return caseIndex.wrap(options.data, self);
                    },
                },
            };
        },
        wrap: function (data, caseConfig) {
            var self = {
                caseConfig: caseConfig,
                actionType: 'open',
            };
            ko.mapping.fromJS(data, openCaseAction.mapping(self), self);
            self.hasPrivilege = true;

            // for compatibility with common templates
            // template: case-config:condition
            self.allow = {
                repeats: function () {
                    return true;
                },
            };

            self.warn_blank_case_tag = ko.observable(false);

            self.disable_tag = ko.computed(function () {
                return false;
            });

            self.suggestedProperties = ko.computed(function () {
                return caseConfigUtils.filteredSuggestedProperties(
                    actionBase.suggestedProperties(self, false),
                    self.case_properties()
                );
            });

            self.validate = ko.computed(function () {
                return actionBase.validate(self, self.case_type(), self.case_tag());
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
                        self.case_indices.push(caseIndex.wrap({
                            tag: gettext('Select parent'),
                            reference_id: 'parent',
                            relationship: 'child',
                            relationship_question: '',
                        }));
                    } else {
                        self.case_indices.removeAll();
                    }
                },
            });

            self.addCaseIndex = function () {
                /**
                 * Copy newCaseIndex form values, and push them to parents array.
                 *
                 * Reference in 'data-bind="with: newCaseIndex"' does not change, so
                 * we need to copy values to another instance, and then reset the
                 * values in the form.
                 */
                self.case_indices.push(caseIndex.wrap({
                    tag: '',
                    reference_id: 'parent',
                    relationship: 'child',
                    relationship_question: '',
                }));
            };

            self.removeCaseIndex = function (viewModel) {
                self.case_indices.remove(viewModel);
            };

            self.case_tag = actionBase.case_tag(self);

            self.close_case = ko.computed(actionBase.close_case(self));

            self.header = ko.computed(function () {
                return actionBase.header(self);
            });

            self.propertyCounts = ko.computed(actionBase.propertyCounts(self));

            self.name_update = ko.computed(function () {
                try {
                    return _(self.case_properties()).find(function (p) {
                        return p.key() === 'name' && p.required();
                    }).path();
                } catch (e) {
                    return null;
                }
            });

            self.repeat_context = function () {
                return self.caseConfig.get_repeat_context(self.name_update());
            };

            self.addProperty = function () {
                self.case_properties.push(caseProperty.wrap({
                    key: '',
                    path: '',
                    required: false,
                }, self));
            };

            self.removeProperty = function (property) {
                self.case_properties.remove(property);
                self.caseConfig.saveButton.fire('change');
            };

            self.relationshipTypes = actionBase.relationshipTypes;

            self.moveable = ko.computed(function () {
                // open case actions are always moveable as they explicitly define their case tags
                // instead of relying on the previously defined case action
                return true;
            });

            var addCircular = function () {
                self.allow_subcase = ko.computed(function () {
                    return self.case_indices || self.caseConfig.caseConfigViewModel.getCaseTags('subcase', self).length > 0;
                });
                self.validate_subcase = ko.computed(function () {
                    if (!self.caseConfig.caseConfigViewModel) {
                        return;
                    }
                    if (!self.case_indices) {
                        return null;
                    }
                    for (var i = 0; i < self.case_indices.length; i++) {
                        var caseIndex = self.case_indices[i];
                        var parent = self.caseConfig.caseConfigViewModel.getActionFromTag(caseIndex.tag());
                        if (!parent) {
                            return gettext("Subcase parent reference is missing");
                        } else if (!caseIndex.reference_id()) {
                            return gettext('Parent reference ID required for subcases: ') + caseIndex.tag();
                        } else if (parent.actionType === 'open') {
                            if (!parent.repeat_context()) {
                                return null;
                            } else if (!self.repeat_context() ||
                                // manual string startsWith
                                self.repeat_context().lastIndexOf(parent.repeat_context(), 0) === 0) {
                                return gettext('Subcase must be in same repeat context as parent "') + caseIndex.tag() + '".';
                            }
                        }
                    }
                    return null;
                });
            };
            // hacky way to prevent trying to access caseConfigViewModel before it is defined
            if (!self.caseConfig.caseConfigViewModel) {
                _.delay(addCircular);
            } else {
                addCircular();
            }

            // needed for compatibility with shared templates
            self.searchAndFilter = false;
            self.visible_case_properties = ko.computed(function () {
                return self.case_properties();
            });
            self.saveOnlyEditedFormFieldsEnabled = toggles.toggleEnabled("SAVE_ONLY_EDITED_FORM_FIELDS");

            return self;
        },
        unwrap: function (self) {
            self.case_properties.remove(function (prop) {
                return prop.isBlank();
            });
            if (self.case_indices().length > 0 && !self.allow_subcase()) {
                self.case_indices.removeAll();
            }
            actionBase.clean_condition(self.open_condition);
            actionBase.clean_condition(self.close_condition);
            var action = ko.mapping.toJS(self, openCaseAction.mapping(self));
            var x = caseConfigUtils.propertyArrayToDict(['name'], action.case_properties);
            action.case_properties = x[0];
            action.name_update = x[1].name;
            action.repeat_context = self.repeat_context();
            return action;
        },
    };

    var autoSelect = {
        mapping: {
            include: ['mode', 'value_source', 'value_key'],
        },
        wrap: function (data, action) {
            var self = ko.mapping.fromJS(data, autoSelect.mapping);
            self.action = action;
            self.isBlank = ko.computed(function () {
                return !self.value_source() && !self.value_key();
            });

            self.mode.subscribe(function () {
                self.value_source('');
                self.value_key('');
            });
            return self;
        },
    };

    var loadCaseFromFixture = {
        mapping: {
            include: [
                'fixture_nodeset',
                'fixture_tag',
                'fixture_variable',
                'auto_select_fixture',
                'case_property',
                'auto_select',
                'arbitrary_datum_id',
                'arbitrary_datum_function',
            ],
        },
        wrap: function (data, action) {
            var self = _.extend({}, action, ko.mapping.fromJS(data, loadCaseFromFixture.mapping));
            self.isBlank = ko.computed(function () {
                return !self.fixture_nodeset() &&
                    !self.fixture_tag() &&
                    !self.fixture_variable() &&
                    !self.case_property() &&
                    !self.auto_select();
            });

            self.validate = ko.computed(function () {
                var caseType = self.case_type,
                    caseTag = self.case_tag;
                if (!self.caseConfig.caseConfigViewModel) {
                    return;
                }
                if (!caseType) {
                    return gettext("Case Type required");
                }
                if (caseTag) {
                    if (!/^[a-zA-Z][\w_-]*(\/[a-zA-Z][\w_-]*)*$/.test(caseTag)) {
                        return gettext("Case Tag: only letters, numbers, '-', and '_' allowed");
                    }
                    var tags = self.caseConfig.caseConfigViewModel.getCaseTags('all');
                    if (_.where(tags, { value: caseTag }).length > 1) {
                        return gettext("Case Tag already in use");
                    }
                }
                return null;
            });

            return self;
        },
    };

    return {
        loadUpdateAction: loadUpdateAction,
        openCaseAction: openCaseAction,
    };
});

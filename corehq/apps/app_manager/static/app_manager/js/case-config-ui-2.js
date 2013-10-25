/*globals $, COMMCAREHQ */

var CaseConfig = (function () {
    "use strict";


    var utils = {
        getDisplay: function (question, MAXLEN) {
            return utils.getLabel(question, MAXLEN) + " (" + question.value + ")";
        },
        getLabel: function (question, MAXLEN) {
            return utils.truncateLabel((question.repeat ? '- ' : '') + question.label, question.tag == 'hidden' ? ' (Hidden)' : '', MAXLEN);
        },
        truncateLabel: function (label, suffix, MAXLEN) {
            suffix = suffix || "";
            var MAXLEN = MAXLEN || 40,
                maxlen = MAXLEN - suffix.length;
            return ((label.length <= maxlen) ? (label) : (label.slice(0, maxlen) + "...")) + suffix;
        },
        escapeQuotes: function (string) {
            return string.replace(/'/g, "&apos;").replace(/"/g, "&quot;");
        },
        action_is_active: function (action) {
            return action && action.condition && (action.condition.type === "if" || action.condition.type === "always");
        }
    };

    ko.bindingHandlers.questionsSelect = {
        init: function (element, valueAccessor) {
            $(element).addClass('input-large');
            $(element).after('<div class="alert alert-error"></div>');
        },
        update: function (element, valueAccessor, allBindingsAccessor) {
            var optionObjects = ko.utils.unwrapObservable(valueAccessor());
            var allBindings = ko.utils.unwrapObservable(allBindingsAccessor());
            var value = ko.utils.unwrapObservable(allBindings.value);
            var $warning = $(element).next();
            if (value && !_.some(optionObjects, function (option) {
                        return option.value === value;
                    })) {
                var option = {
                    label: 'Unidentified Question (' + value + ')',
                    value: value
                };
                optionObjects = [option].concat(optionObjects);
                $warning.show().text('We cannot find this question in the form. It is likely that you deleted or renamed the question. Please choose a valid question from the dropdown.');
            } else {
                $warning.hide();
            }
            _.delay(function () {
                $(element).select2({
                    placeholder: 'Select a Question',
                    data: {
                        results: _(optionObjects).map(function (o) {
                            return {id: o.value, text: utils.getDisplay(o), question: o};
                        })
                    },
                    formatSelection: function (o) {
                        return utils.getDisplay(o.question);
                    },
                    formatResult: function (o) {
                        return utils.getDisplay(o.question, 90);
                    },
                    dropdownCssClass: 'bigdrop'
                });
            });
            allBindings.optstrText = utils.getLabel;
        }
    };


    var CaseConfig = function (params) {
        var self = this;
        var i;

        self.home = params.home;
        self.actions = (function (a) {
            var actions = {}, i;
            _(action_names).each(function (action_name) {
                actions[action_name] = a[action_name];
            });
            actions.subcases = a.subcases;
            return actions;
        }(params.actions));
        self.questions = params.questions;
        self.edit = params.edit;
        self.save_url = params.save_url;
        // `requires` is a ko observable so it can be read by another UI
        self.requires = params.requires;
        self.caseType = params.caseType;
        self.reserved_words = params.reserved_words;
        self.moduleCaseTypes = params.moduleCaseTypes;
        self.propertiesMap = {};
        self.utils = utils;

        self.setPropertiesMap = function (propertiesMap) {
            _(self.moduleCaseTypes).each(function (case_type) {
                if (!_(propertiesMap).has(case_type)) {
                    propertiesMap[case_type] = [];
                }
                propertiesMap[case_type].sort();
            });
            _(propertiesMap).each(function (properties, case_type) {
                if (_(self.propertiesMap).has(case_type)) {
                    self.propertiesMap[case_type](properties);
                } else {
                    self.propertiesMap[case_type] = ko.observableArray(properties);
                }
            });
            self.propertiesMap = ko.mapping.fromJS(params.propertiesMap);
        };
        self.setPropertiesMap(params.propertiesMap);

        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: "You have unchanged case settings",
            save: function () {
                var requires = self.caseConfigViewModel.actionType() === 'update' ? 'case' : 'none';
                var subcases;
                if (self.caseConfigViewModel.actionType() === 'none') {
                    subcases = [];
                } else {
                    subcases = _(self.caseConfigViewModel.subcases()).map(HQOpenSubCaseAction.from_case_transaction);
                }
                var actions = JSON.stringify(_(self.actions).extend(
                    HQFormActions.from_case_transaction(self.caseConfigViewModel.case_transaction),
                    {subcases: subcases}
                ));

                self.saveButton.ajax({
                    type: 'post',
                    url: self.save_url,
                    data: {
                        requires: requires,
                        actions: actions
                    },
                    dataType: 'json',
                    success: function (data) {
                        COMMCAREHQ.app_manager.updateDOM(data.update);
                        self.requires(requires);
                        self.setPropertiesMap(data.propertiesMap);
                    }
                });
            }
        });

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
        self.caseConfigViewModel = new CaseConfigViewModel(self);

        self.ensureBlankProperties = function () {
            self.caseConfigViewModel.case_transaction.ensureBlankProperties();
            _(self.caseConfigViewModel.subcases()).each(function (case_transaction) {
                case_transaction.ensureBlankProperties();
            });
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
        }
    };
    CaseConfig.prototype = utils;


    var CaseConfigViewModel = function (caseConfig) {
        var self = this;

        self.caseConfig = caseConfig;
        self.edit = ko.observable(self.caseConfig.edit);
        self.moduleCaseTypes = caseConfig.moduleCaseTypes;
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
            if (caseType === self.caseConfig.caseType) {
                label = '*' + label;
            }
            return label
        };
        self.case_transaction = HQFormActions.to_case_transaction(caseConfig.actions, caseConfig);
        self.subcases = ko.observableArray(
            _(caseConfig.actions.subcases).map(function (subcase) {
                return HQOpenSubCaseAction.to_case_transaction(subcase, caseConfig)
            })
        );
        self.addSubCase = function () {
            self.subcases.push(HQOpenSubCaseAction.to_case_transaction({}, caseConfig));
        };
        self.removeSubCase = function (subcase) {
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
                } else if (has_subcases) {
                    return 'open-other';
                } else {
                    return 'none';
                }
            }()));

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
    };


    var CaseTransaction = {
        mapping: function (self) {
            return {
                include: [
                    'case_type',
                    'reference_id',
                    'condition',
                    'case_properties',
                    'case_preload',
                    'close_condition',
                    'allow'
                ],
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
            }
        },
        wrap: function (data, caseConfig) {
            var self = {};
            ko.mapping.fromJS(data, CaseTransaction.mapping(self), self);
            self.case_type(self.case_type() || caseConfig.caseType);
            self.caseConfig = caseConfig;

            // link self.case_name to corresponding path observable
            // in case_properties for convenience
            try {
                self.case_name = _(self.case_properties()).find(function (p) {
                    return p.key() === 'name' && p.required();
                }).path;
            } catch (e) {
                self.case_name = null;
            }
            self.suggestedProperties = ko.computed(self.suggestedProperties, self);

            self.addProperty = function () {
                var property = CaseProperty.wrap({
                    path: '',
                    key: '',
                    required: false
                }, self);

                self.case_properties.push(property);
            };

            self.removeProperty = function (property) {
                self.case_properties.remove(property);
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

            if (self.case_preload) {
                self.addPreload = function () {
                    var property = CasePreload.wrap({
                        path: '',
                        key: '',
                        required: false
                    }, self);

                    self.case_preload.push(property);
                };

                self.removePreload = function (property) {
                    self.case_preload.remove(property);
                };

                self.preloadCounts = ko.computed(function () {
                    var count = {};
                    _(self.case_preload()).each(function (p) {
                        var path = p.path();
                        if (!count.hasOwnProperty(path)) {
                            count[path] = 0;
                        }
                        return count[path] += 1;
                    });
                    return count;
                });
            }

            self.repeat_context = function () {
                return self.caseConfig.get_repeat_context(self.case_name());
            };

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
                }
            });

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
                    self.case_properties.splice(0, 0, CaseProperty.wrap({
                        path: '',
                        key: key,
                        required: true
                    }, self));
                });
            };

            self.unwrap = function () {
                CaseTransaction.unwrap(self);
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

            return self;
        },
        unwrap: function (self) {
            return ko.mapping.toJS(self, CaseTransaction.mapping(self));
        }
    };


    var CasePropertyBase = {
        mapping: {
            include: ['key', 'path', 'required']
        },
        wrap: function (data, case_transaction) {
            var self = ko.mapping.fromJS(data, CaseProperty.mapping);
            self.case_transaction = case_transaction;
            self.isBlank = ko.computed(function () {
                return !self.key() && !self.path();
            });
            return self;
        }
    };

    var CaseProperty = {
        mapping: CasePropertyBase.mapping,
        wrap: function (data, case_transaction) {
            var self = CasePropertyBase.wrap(data, case_transaction);
            self.defaultKey = ko.computed(function () {
                var path = self.path() || '';
                var value = path.split('/');
                value = value[value.length-1];
                return value;
            });
            self.repeat_context = function () {
                return case_transaction.caseConfig.get_repeat_context(self.path());
            };
            self.validate = ko.computed(function () {
                if (self.path() || self.key()) {
                    if (case_transaction.propertyCounts()[self.key()] > 1) {
                        return "Property updated by two questions";
                    } else if (case_transaction.caseConfig.reserved_words.indexOf(self.key()) !== -1) {
                        return '<strong>' + self.key() + '</strong> is a reserved word';
                    } else if (self.repeat_context() && self.repeat_context() !== case_transaction.repeat_context()) {
                        return 'Inside the wrong repeat!'
                    }
                }
                return null;
            });
            return self;
        }
    };

    var CasePreload = {
        wrap: function (data, case_transaction) {
            var self = CasePropertyBase.wrap(data, case_transaction);
            self.defaultKey = ko.computed(function () {
                return '';
            });
            self.validateProperty = ko.computed(function () {
                if (self.path() || self.key()) {
                    if (case_transaction.caseConfig.reserved_words.indexOf(self.key()) !== -1) {
                        return '<strong>' + self.key() + '</strong> is a reserved word';
                    }
                }
                return null;
            });
            self.validateQuestion = ko.computed(function () {
                if (self.path()) {
                    if (case_transaction.preloadCounts()[self.path()] > 1) {
                        return "Two properties load to the same question";
                    }
                }
                return null;
            });
            return self;
        }
    };

    var DEFAULT_CONDITION = {
        type: 'always',
        question: null,
        answer: null
    };

    var propertyDictToArray = function (required, property_dict, caseConfig, keyIsPath) {
        var property_array = _(property_dict).map(function (value, key) {
            return {
                path: !keyIsPath ? value : key,
                key: !keyIsPath ? key : value,
                required: false
            };
        });
        property_array = _(property_array).sortBy(function (property) {
            return caseConfig.questionScores[property.path] * 2 + (property.required ? 0 : 1);
        });
        return required.concat(property_array);
    };

    var propertyArrayToDict = function (required, property_array, keyIsPath) {
        var property_dict = {},
            extra_dict = {};
        _(property_array).each(function (case_property) {
            var key = case_property[!keyIsPath ? 'key' : 'path'];
            var path = case_property[!keyIsPath ? 'path' : 'key'];
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

    var HQFormActions = {
        normalize: function (o) {
            var self = {};
            self.open_case = {
                condition: (o.open_case || {}).condition || DEFAULT_CONDITION,
                name_path: (o.open_case || {}).name_path || ''
            };
            self.update_case = {
                update: (o.update_case || {}).update || {}
            };
            self.case_preload = {
                preload: (o.case_preload || {}).preload || {}
            };
            self.close_case = {
                condition: (o.close_case || {}).condition || DEFAULT_CONDITION
            };
            return self;
        },
        to_case_transaction: function (o, caseConfig) {
            var self = HQFormActions.normalize(o);
            var required_properties = caseConfig.requires() === 'none' && !o.update_case.update.name ? [{
                key: 'name',
                path: self.open_case.name_path,
                required: true
            }] : [];
            var case_properties = propertyDictToArray(
                required_properties,
                self.update_case.update,
                caseConfig
            );
            var case_preload = propertyDictToArray(
                [],
                self.case_preload.preload,
                caseConfig,
                true
            );
            var x = CaseTransaction.wrap({
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
                }
            }, caseConfig);
            _.delay(function () {
                x.allow = {
                    condition: ko.computed(function () {
                        return caseConfig.caseConfigViewModel.actionType() === 'open';
                    }),
                    close_condition: ko.computed(function () {
                        return caseConfig.caseConfigViewModel.actionType() === 'update';
                    }),
                    case_preload: ko.computed(function () {
                        return caseConfig.caseConfigViewModel.actionType() === 'update';
                    }),
                    repeats: function () {
                        return false;
                    }
                };
            });
            return x;
        },
        from_case_transaction: function (case_transaction) {
            var o = CaseTransaction.unwrap(case_transaction);
            var x = propertyArrayToDict(['name'], o.case_properties);
            var case_properties = x[0], case_name = x[1].name;
            var case_preload = propertyArrayToDict([], o.case_preload, true)[0];
            var open_condition = o.condition;
            var close_condition = o.close_condition;
            var update_condition = DEFAULT_CONDITION;
            var actionType = case_transaction.caseConfig.caseConfigViewModel.actionType();

            if (actionType === 'open') {
                if (open_condition.type === 'never') {
                    open_condition.type = 'always';
                }
            } else {
                open_condition.type = 'never';

            }

            if (actionType === 'open' || actionType === 'update') {
                update_condition.type = 'always';
            } else {
                update_condition.type = 'never';
            }

            return {
                open_case: {
                    condition: open_condition,
                    name_path: case_name
                },
                update_case: {
                    update: case_properties,
                    condition: update_condition
                },
                case_preload: {
                    preload: case_preload,
                    condition: update_condition
                },
                close_case: {
                    condition: close_condition
                }
            };
        }
    };

    var HQOpenSubCaseAction = {
        normalize: function (o) {
            var self = {};
            self.case_type = o.case_type || null;
            self.case_name = o.case_name || null;
            self.reference_id = o.reference_id || null;
            self.case_properties = o.case_properties || {};
            self.condition = o.condition || DEFAULT_CONDITION;
            self.repeat_context = o.repeat_context;
            return self;
        },
        to_case_transaction: function (o, caseConfig) {
            var self = HQOpenSubCaseAction.normalize(o);
            var case_properties = propertyDictToArray([{
                    path: self.case_name,
                    key: 'name',
                    required: true
                }], self.case_properties, caseConfig);


            return CaseTransaction.wrap({
                case_type: self.case_type,
                reference_id: self.reference_id,
                case_properties: case_properties,
                condition: self.condition,
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
                    close_condition: function () {
                        return false;
                    },
                    case_preload: function () {
                        return false;
                    },
                    repeats: function () {
                        return true;
                    },
                    parentProperties: function () {
                        return false;
                    }
                }
            }, caseConfig);
        },
        from_case_transaction: function (case_transaction) {
            var o = CaseTransaction.unwrap(case_transaction);
            var x = propertyArrayToDict(['name'], o.case_properties);
            var case_properties = x[0], case_name = x[1].name;

            return {
                case_name: case_name,
                case_type: o.case_type,
                case_properties: case_properties,
                reference_id: o.reference_id,
                condition: o.condition,
                repeat_context: case_transaction.repeat_context()
            };
        }
    };

    var action_names = ["open_case", "update_case", "close_case", "case_preload"];
    CaseConfig.prototype.getQuestions = function (filter, excludeHidden, includeRepeat) {
        // filter can be "all", or any of "select1", "select", or "input" separated by spaces
        var i, options = [],
            q;
        excludeHidden = excludeHidden || false;
        includeRepeat = includeRepeat || false;
        filter = filter.split(" ");
        if (!excludeHidden) {
            filter.push('hidden');
        }
        for (i = 0; i < this.questions.length; i += 1) {
            q = this.questions[i];
            if (filter[0] === "all" || filter.indexOf(q.tag) !== -1) {
                if (includeRepeat || !q.repeat) {
                    options.push(q);
                }
            }
        }
        return options;
    };
    CaseConfig.prototype.getAnswers = function (condition) {
        var i, q, o, value = condition.question,
            found = false,
            options = [];
        for (i = 0; i < this.questions.length; i += 1) {
            q = this.questions[i];
            if (q.value === value) {
                found = true;
                break;
            }
        }
        if (found && q.options) {
            for (i = 0; i < q.options.length; i += 1) {
                o = q.options[i];
                options.push(o);
            }
        }
        return options;
    };
    return {
        CaseConfig: CaseConfig
    };
}());
/*globals $, EJS, COMMCAREHQ */

/*
This file was copied from case-config-ui-1.js, and then edited.
All additions are done using knockout, and can eventually replace all the old code.
 */

var CaseConfig = (function () {
    "use strict";


    var utils = {
        getLabel: function (question) {
            return utils.truncateLabel((question.repeat ? '- ' : '') + question.label, question.tag == 'hidden' ? ' (Hidden)' : '');
        },
        truncateLabel: function (label, suffix) {
            suffix = suffix || "";
            var MAXLEN = 40,
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


    var CaseConfig = function (params) {
        var self = this;
        var i, $form, ejs_urls = params.ejs_urls;

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
        self.utils = utils;

        self.initEJS = function () {
            var makeEJS = function (url) {
                return new EJS({
                    url: url,
                    type: "["
                });
            };
            self.action_templates = {};
            for (var slug in ejs_urls) {
                if (ejs_urls.hasOwnProperty(slug) && slug !== 'action_templates') {
                    self[slug] = makeEJS(ejs_urls[slug]);
                }
            }
            _(action_names).each(function (action_name) {
                self.action_templates[action_name] = makeEJS(
                    ejs_urls.action_templates[action_name]
                );
            });
        };
        self.initEJS();
        self.initSaving = function () {

        };
        $form = $('<form method="POST"/>').attr('action', self.save_url).append(
            $('<textarea id="casexml_json" class="hidden" name="actions"/>')
        );

        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: "You have unchanged case settings",
            save: function () {
                self.saveButton.ajax({
                    type: 'post',
                    url: self.save_url,
                    data: {
                        requires: self.requires(),
                        actions: JSON.stringify(_(self.actions).extend({
                            subcases: _(self.subCasesViewModel.subcases()).map(HQOpenSubCaseAction.from_case_transaction)
                        }))
                    },
                    dataType: 'json',
                    success: function (data) {
                        COMMCAREHQ.app_manager.updateDOM(data.update);
                    }
                });
            }
        });
        self.change = function () {
            self.saveButton.fire('change');
        };
        $form.appendTo(self.home.find('.old-case-config'));
        self.subhome = $('<div/>').prependTo($form);

        var questionMap = {};
        _(self.questions).each(function (question) {
            questionMap[question.value] = question;
        });
        self.get_repeat_context = function(path) {
            if (path) {
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
        self.subCasesViewModel = new SubCasesViewModel(self);
        ko.applyBindings(self, $('#case-config-ko').get(0));
    };
    CaseConfig.prototype = utils;


    var SubCasesViewModel = function (caseConfig) {
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
        self.subcases = ko.observableArray(
            _(self.caseConfig.actions.subcases).map(function (subcase) {
                return HQOpenSubCaseAction.to_case_transaction(subcase, caseConfig)
            })
        );
        self.addSubCase = function () {
            self.subcases.push(HQOpenSubCaseAction.to_case_transaction({}, self.caseConfig));
        };
        self.removeSubCase = function (subcase) {
            self.subcases.remove(subcase);
            self.caseConfig.change();
        };
    };


    var CaseTransaction = {
        mapping: function (self) {
            return {
                include: ['case_type', 'condition', 'case_properties'],
                    case_properties: {
                    create: function (options) {
                        return CaseProperty.wrap(options.data, self);
                    }
                }
            }
        },
        wrap: function (data, caseConfig) {
            var self = {};
            ko.mapping.fromJS(data, CaseTransaction.mapping(self), self);

            self.caseConfig = caseConfig;

            // link self.case_name to corresponding path observable
            // in case_properties for convenience
            self.case_name = _(self.case_properties()).find(function (p) {
                return p.key() === 'name' && p.required();
            }).path;

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
                self.caseConfig.change();
            };
            self.propertyCounts = ko.computed(function () {
                var count = {};
                ko.utils.arrayForEach(self.case_properties(), function (p) {
                    var key = p.keyVal();
                    return count[key] = count[key] ? count[key] + 1 : 1;
                });
                return count;
            });
            self.repeat_context = function () {
                return self.caseConfig.get_repeat_context(self.case_name());
            };
            self.unwrap = function () {
                CaseTransaction.unwrap(self);
            };
            return self;
        },
        unwrap: function (self) {
            return ko.mapping.toJS(self, CaseTransaction.mapping(self));
        }
    };


    var CaseProperty = {
        mapping: {
            include: ['key', 'path', 'required']
        },
        wrap: function (data, case_transaction) {
            var self = ko.mapping.fromJS(data, CaseProperty.mapping);
            self.defaultKey = ko.computed(function () {
                var path = self.path() || '';
                var value = path.split('/');
                value = value[value.length-1];
                return value;
            });
            self.keyVal = ko.computed(function () {
                return self.key() || self.defaultKey();
            });
            self.repeat_context = function () {
                return case_transaction.caseConfig.get_repeat_context(self.path());
            };
            self.validate = ko.computed(function () {
                if (self.path() || self.keyVal()) {
                    if (case_transaction.propertyCounts()[self.keyVal()] > 1) {
                        return "Duplicate property";
                    } else if (case_transaction.caseConfig.reserved_words.indexOf(self.keyVal()) !== -1) {
                        return '<strong>' + self.keyVal() + '</strong> is a reserved word';
                    } else if (self.repeat_context() && self.repeat_context() !== case_transaction.repeat_context()) {
                        return 'Inside the wrong repeat!'
                    }
                }
                return null;
            });
            return self;
        }
    };


    var HQOpenSubCaseAction = {
        normalize: function (o) {
            var self = {};
            self.case_type = o.case_type || null;
            self.case_name = o.case_name || null;
            self.case_properties = o.case_properties || {};
            self.condition = o.condition || {
                type: 'always',
                question: null,
                answer: null
            };
            self.repeat_context = o.repeat_context;
            return self;
        },
        to_case_transaction: function (o, caseConfig) {
            var self = HQOpenSubCaseAction.normalize(o);
            var case_properties = [{
                path: self.case_name,
                key: 'name',
                required: true
            }];

            for (var key in self.case_properties) {
                if (self.case_properties.hasOwnProperty(key)) {
                    case_properties.push({
                        path: self.case_properties[key],
                        key: key,
                        required: false
                    });
                }
            }
            case_properties = _.sortBy(case_properties, function (property) {
                return caseConfig.questionScores[property.path];
            });
            return CaseTransaction.wrap({
                case_type: self.case_type,
                case_properties: case_properties,
                condition: self.condition
            }, caseConfig);
        },
        from_case_transaction: function (case_transaction) {
            var o = CaseTransaction.unwrap(case_transaction);
            var case_properties = {}, case_name;
            _(o.case_properties).each(function (case_property) {
                var key = case_property.key;
                var path = case_property.path;
                if (key || path) {
                    if (key === 'name' && case_property.required) {
                        case_name = path;
                    } else {
                        case_properties[key] = path;
                    }
                }
            });
            return {
                case_name: case_name,
                case_type: o.case_type,
                case_properties: case_properties,
                condition: o.condition,
                repeat_context: case_transaction.repeat_context()
            };
        }
    };

    var action_names = ["open_case", "update_case", "close_case", "case_preload"];
    CaseConfig.prototype.render = function () {
        var self = this;
        var i;
        _(action_names).each(function (action_name) {
            self.actions[action_name] = self.actions[action_name] || {
                condition: {
                    type: "never"
                }
            };
        });
        self.template.update(self.subhome.get(0), self);
        COMMCAREHQ.initBlock(self.subhome);
        $('.action-checkbox').each(function () {
            var container = $(this).parent().next('.well');
            if (!$(this).is(':checked')) {
                container.hide();
            }
        });
    };
    CaseConfig.prototype.init = function () {
        var self = this;
        if (self.questions.length && self.edit) {
            self.home.delegate('input:not(.action-checkbox), select', 'change textchange', function () {
                // recompute casexml_json
                self.refreshActions();
                self.render();
                self.refreshActions();
                self.render();
                self.change();
            }).delegate('input.action-checkbox', 'change', function () {
                var container = $(this).parent().next('.well');
                if ($(this).is(':checked')) {
                    container.slideDown();
                } else {
                    container.slideUp();
                }
                self.refreshActions();
                self.change();
            });
        }
        this.render();
    };
    CaseConfig.prototype.sortByQuestions = function (map, keysOrValues) {
        var self = this, pairs = _.pairs(map);
        return _(pairs).sortBy(function (pair) {
            var path = keysOrValues === 'keys' ? pair[0] : pair[1];
            return self.questionScores[path];
        });
    };
    CaseConfig.prototype.renderCondition = function (condition) {
        return this.condition_ejs.render({
            casexml: this,
            condition: condition
        });
    };
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
    CaseConfig.prototype.renderOptions = function (options, value, name, allowNull) {
        if (allowNull === undefined) {
            allowNull = true;
        }
        return this.options_ejs.render({
            casexml: this,
            options: options,
            value: value,
            name: name,
            allowNull: allowNull
        });
    };
    CaseConfig.prototype.renderQuestions = function (filter) {
        var options = this.getQuestions(filter),
            html = "";
        options.forEach(function (o) {
            html += "<option value='" + o.value + "' title='" + utils.escapeQuotes(o.label) + "'>" + this.truncateLabel(o.label) + "</option>";
        });
        return html;
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
    CaseConfig.prototype.renderChecked = function (action) {
        if (this.action_is_active(action)) {
            return 'checked="true"';
        } else {
            return "";
        }
    };

    CaseConfig.prototype.refreshActions = function () {
        var self = this;

        function lookup(root, key) {
            return $(root).find('[name="' + key + '"]').attr('value');
        }
        self.requires.subscribe(function () {
            self.render();
        });
        $(".casexml .action").each(function () {

            var $checkbox = $(this).find('input[type="checkbox"].action-checkbox'),
                id = $checkbox.attr('id').replace('-', '_'),
                action = {
                    "condition": {
                        "type": "never"
                    }
                };

            if (!$checkbox.is(":checked")) {
                self.actions[id] = action;
                return;
            }


            if (id === "open_case") {
                action.name_path = lookup(this, 'name_path');
                action.external_id = lookup(this, 'external_id');
            } else if (id === "update_case") {
                action.update = {};
                $('.action-update', this).each(function () {
                    var key = lookup(this, "action-update-key"),
                        val = lookup(this, "action-update-value");
                    if (key || val) {
                        action.update[key] = val;
                    }
                });
            } else if (id === "case_preload") {
                action.preload = {};
                $('.action-update', this).each(function () {
                    var propertyName = lookup(this, "action-update-key"),
                        nodeset = lookup(this, "action-update-value");
                    if (propertyName || nodeset) {
                        action.preload[nodeset] = propertyName;
                    }
                });
            }
            action.condition = {
                'type': 'always'
            }; // default value
            $('.condition', this).each(function () { // there is only one
                // action.condition = {};
                //                if($checkbox.is(":checked")) {
                //                    action.condition.type = "never";
                //                }
                if ($('input[name="if"]', this).is(':checked')) {
                    action.condition.type = "if";
                } else {
                    action.condition.type = 'always';
                }
                if (action.condition.type === 'if') {
                    action.condition.question = lookup(this, 'condition-question');
                    action.condition.answer = lookup(this, 'condition-answer');
                }
            });
            self.actions[id] = action;
        });
    };

    CaseConfig.prototype.renderAction = function (action_type, label) {
        var html = this.action_ejs.render({
            casexml: this,
            id: action_type.replace("_", "-"),
            action_type: action_type,
            label: label,
            action_body: this.action_templates[action_type].render(this)
        });
        return html;
    };
    CaseConfig.prototype.hasActions = function () {
        var a;
        for (a in this.actions) {
            if (this.actions.hasOwnProperty(a)) {
                if (this.action_is_active(this.actions[a])) {
                    return true;
                }
            }
        }
    };
    CaseConfig.prototype.renderPropertyList = function (map, keyType, reservedWords, showSuggestion) {
        showSuggestion = showSuggestion === undefined ? false : showSuggestion;
        return this.propertyList_ejs.render({
            map: map,
            keyType: keyType,
            showSuggestion: showSuggestion,
            casexml: this,
            reservedWords: reservedWords
        });
    };

    return {
        CaseConfig: CaseConfig
    };
}());
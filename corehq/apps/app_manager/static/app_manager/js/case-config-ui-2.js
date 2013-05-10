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
                            subcases: _(self.subCasesViewModel.subcases()).map(SubCase.unwrap)
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
                return SubCase.wrap(subcase, self.caseConfig);
            })
        );
        self.addSubCase = function () {
            self.subcases.push(SubCase.wrap({}));
        };
        self.removeSubCase = function (subcase) {
            self.subcases.remove(subcase);
            self.caseConfig.change();
        };
        self.toJS = function () {
            self.actions
        }
    };


    var SubCase = {
        transforms: [
            {
                read: function (o, caseConfig) {
                    var case_properties = [];

                    for (var key in o.case_properties) {
                        if (o.case_properties.hasOwnProperty(key)) {
                            case_properties.push({
                                path: o.case_properties[key],
                                key: key
                            });
                        }
                    }
                    case_properties = _.sortBy(case_properties, function (property) {
                        return caseConfig.questionScores[property.path];
                    });
                    o.case_properties = case_properties;
                },
                write: function (o, self) {
                    var case_properties = {};
                    for (var i = 0; i < o.case_properties.length; i++) {
                        if (self.case_properties()[i].keyVal() || o.case_properties[i].path) {
                            case_properties[self.case_properties()[i].keyVal()] = o.case_properties[i].path;
                        }
                    }
                    o.case_properties = case_properties;
                }
            },
            function (o) {
                o.case_type = o.case_type || null;
                o.case_name = o.case_name || null;
                o.condition = o.condition || {
                    type: 'always',
                    question: null,
                    answer: null
                };
            },
            {
                write: function (o, self) {
                    o.repeat_context = self.repeat_context();
                }
            }
        ],
        wrap: function (o, caseConfig) {
            _(SubCase.transforms).each(function (transform) {
                if (transform.hasOwnProperty('read')) {
                    transform.read(o, caseConfig);
                } else {
                    if (typeof transform === 'function') {
                        transform(o);
                    }
                }
            });
            var case_properties = o.case_properties;
            o.case_properties = [];
            var self = ko.mapping.fromJS(o);
            self.caseConfig = caseConfig;

            self.addProperty = function () {
                var property = CaseProperty.wrap({
                    path: '',
                    key: ''
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
                SubCase.unwrap(self);
            };

            self.case_properties(
                _(case_properties).map(function (property) {
                    return CaseProperty.wrap(property, self);
                })
            );

            return self;
        },
        unwrap: function (self) {
            var o = ko.mapping.toJS(self);
            ko.utils.arrayForEach(SubCase.transforms, function (transform) {
                if (transform.hasOwnProperty('write')) {
                    transform.write(o, self);
                }
            });
            return o;
        }
    };


    var CaseProperty = {
        wrap: function (o, subcase) {
            var self = ko.mapping.fromJS(o);
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
                return subcase.caseConfig.get_repeat_context(self.path());
            };
            self.validate = ko.computed(function () {
                if (self.path() || self.keyVal()) {
                    if (subcase.propertyCounts()[self.keyVal()] > 1) {
                        return "Duplicate property";
                    } else if (subcase.caseConfig.reserved_words.indexOf(self.keyVal()) !== -1) {
                        return '<strong>' + self.keyVal() + '</strong> is a reserved word';
                    } else if (self.repeat_context() && self.repeat_context() !== subcase.repeat_context()) {
                        return 'Inside the wrong repeat!'
                    }
                }
                return null;
            });
            return self;
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
        console.log(self.renderChecked);
        self.template.update(self.subhome.get(0), self);
        console.log('ohi');
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
            console.log('weeee!');
            return 'checked="true"';
        } else {
            console.log('ugh!', action);
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
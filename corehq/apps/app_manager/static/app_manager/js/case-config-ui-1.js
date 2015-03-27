/*globals $, EJS, COMMCAREHQ */
var CaseConfig = (function () {
    "use strict";
    var action_names = ["open_case", "update_case", "close_case", "open_referral", "update_referral", "close_referral", "case_preload", "referral_preload"],
        CaseConfig = function (params) {
            var i, $form;

            this.home = params.home;
            this.actions = params.actions;
            this.questions = params.questions;
            this.save_url = params.save_url;
            this.requires = ko.utils.unwrapObservable(params.requires);
            this.save_requires_url = params.save_requires_url;
            this.template = new EJS({
                url: "/static/app_manager/ejs/casexml.ejs",
                type: "["
            });
            this.condition_ejs = new EJS({
                url: "/static/app_manager/ejs/condition.ejs",
                type: "["
            });
            this.action_ejs = new EJS({
                url: "/static/app_manager/ejs/action.ejs",
                type: "["
            });
            this.options_ejs = new EJS({
                url: "/static/app_manager/ejs/options.ejs",
                type: "["
            });
            this.propertyList_ejs = new EJS({
                url: "/static/app_manager/ejs/propertyList.ejs",
                type: "["
            });
            this.action_templates = {};
            this.reserved_words = params.reserved_words;
            for (i = 0; i < action_names.length; i += 1) {
                this.action_templates[action_names[i]] = new EJS({
                    url: "/static/app_manager/ejs/actions/" + action_names[i] + ".ejs",
                    type: "["
                });
            }
            //        $("#casexml-template").remove();
            $form = $('<form method="POST"/>').attr('action', this.save_url).append(
                $('<textarea id="casexml_json" class="hide" name="actions"/>')
            );

            this.saveButton = COMMCAREHQ.SaveButton.initForm($form, {
                unsavedMessage: "You have unchanged case and referral settings",
                success: function (data) {
                    COMMCAREHQ.app_manager.updateDOM(data.update);
                }
            });
            this.saveButton.ui.appendTo(this.home);
            $form.appendTo(this.home);
            this.subhome = $('<div/>').appendTo($form);
            var questionScores = {};
            _(this.questions).each(function (question, i) {
                questionScores[question.value] = i;
            });
            this.questionScores = questionScores;
        };
    CaseConfig.prototype = {
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



    CaseConfig.prototype.render = function () {
        var i;
        for (i = 0; i < action_names.length; i += 1) {
            this.actions[action_names[i]] = this.actions[action_names[i]] || {
                condition: {
                    type: "never"
                }
            };
        }
        this.template.update(this.subhome.get(0), this);
        COMMCAREHQ.initBlock(this.subhome);
        $('.action-checkbox').each(function () {
            var container = $(this).parent().next('.well');
            if (!$(this).is(':checked')) {
                container.hide();
            }
        });
    };
    CaseConfig.prototype.init = function () {
        var casexml = this;
        if (this.questions.length) {
            this.home.delegate('input:not(.action-checkbox), select', 'change textchange', function () {
                // recompute casexml_json
                casexml.refreshActions();
                casexml.render();
                casexml.refreshActions();
                casexml.render();
                $("#casexml_json").text(JSON.stringify(casexml.actions));
                casexml.saveButton.fire('change');
            }).delegate('input.action-checkbox', 'change', function () {
                var container = $(this).parent().next('.well');
                if ($(this).is(':checked')) {
                    container.slideDown();
                } else {
                    container.slideUp();
                }
                casexml.refreshActions();
                $("#casexml_json").text(JSON.stringify(casexml.actions));
                casexml.saveButton.fire('change');
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
    CaseConfig.prototype.getQuestions = function (filter, excludeHidden) {
        // filter can be "all", or any of "select1", "select", or "input" separated by spaces
        var i, options = [],
            q;
        excludeHidden = excludeHidden || false;
        filter = filter.split(" ");
        if (!excludeHidden) {
            filter.push('hidden');
        }
        for (i = 0; i < this.questions.length; i += 1) {
            q = this.questions[i];
            if (filter[0] === "all" || filter.indexOf(q.tag) !== -1) {
                options.push(q);
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
            html += "<option value='" + o.value + "' title='" + this.escapeQuotes(o.label) + "'>" + this.truncateLabel(o.label) + "</option>";
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
        var actions = {},
            requires;

        function lookup(root, key) {
            return $(root).find('[name="' + key + '"]').attr('value');
        }
        requires = $('[name="requires"]', this.subhome).val();
        if (requires !== this.requires) {
            this.requires = requires;
            this.render();
        }
        $(".casexml .action").each(function () {

            var $checkbox = $(this).find('input[type="checkbox"].action-checkbox'),
                id = $checkbox.attr('id').replace('-', '_'),
                action = {
                    "condition": {
                        "type": "never"
                    }
                };

            if (!$checkbox.is(":checked")) {
                actions[id] = action;
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
            } else if (id === "case_preload" || id === "referral_preload") {
                action.preload = {};
                $('.action-update', this).each(function () {
                    var propertyName = lookup(this, "action-update-key"),
                        nodeset = lookup(this, "action-update-value");
                    if (propertyName || nodeset) {
                        action.preload[nodeset] = propertyName;
                    }
                });
            } else if (id === "open_referral") {
                action.name_path = lookup(this, 'name_path');
                action.followup_date = lookup(this, 'followup_date');
            } else if (id === "update_referral") {
                action.followup_date = lookup(this, 'followup_date');
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
            actions[id] = action;

        });
        this.actions = actions;
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

    return {CaseConfig: CaseConfig};
}());

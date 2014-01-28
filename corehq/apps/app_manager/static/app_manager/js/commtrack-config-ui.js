var action_names = ['case_preload1', 'case_preload2', 'open_subcase'];

var CommTrackConfig = (function () {
    'use strict';

    var Commtrack = function (params) {
        var self = this;

        self.home = params.home;
        self.actions = (function (a) {
            var actions = {}, i;
            _(action_names).each(function (action_name) {
                actions[action_name] = a[action_name];
            });
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
        self.propertiesMap = ko.mapping.fromJS(params.propertiesMap);

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

    return {
        Commtrack: Commtrack
    };
}());

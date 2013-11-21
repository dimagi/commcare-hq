
var CareplanConfig = (function(){
    var Question = {
        wrap: function (data, transaction) {
            var self = ko.mapping.fromJS(data);
            self.transaction = transaction;

            self.validateQuestion = ko.computed(function () {
                if (self.path()) {
                    if (transaction.propertyCounts()[self.path()] > 1) {
                        return "Question is being used twice.";
                    }
                }
                return null;
            });

            return self;
        }
    };

    var CareplanTransaction = {
        mapping: function (self) {
            return {
                include: [
                    'fixedQuestions'
                ],
                fixedQuestions: {
                    create: function (options) {
                        return Question.wrap(options.data, self);
                    }
                }
            }
        },
        wrap: function (data, careplanConfig) {
            var self = {};
            ko.mapping.fromJS(data, CareplanTransaction.mapping(self), self);

            self.propertyCounts = ko.computed(function () {
                var count = {};
                _(self.fixedQuestions()).each(function (p) {
                    var path = p.path();
                    if (!count.hasOwnProperty(path)) {
                        count[path] = 0;
                    }
                    return count[path] += 1;
                });
                return count;
            });

            self.unwrap = function () {
                CareplanTransaction.unwrap(self);
            };

            return self;
        },
        unwrap: function (self) {
            return ko.mapping.toJS(self, CareplanTransaction.mapping(self));
        }
    }

    var Careplan = function(params){
        var self = this;
        self.home = params.home,
        self.edit = params.edit;
        self.save_url = params.save_url;
        self.questions = params.questions;
        self.transaction = CareplanTransaction.wrap({
            fixedQuestions: params.fixedQuestions
        });

        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: "You have unsaved changes",
            save: function () {
                var transaction = CareplanTransaction.unwrap(self.transaction);
                self.saveButton.ajax({
                    type: 'post',
                    url: self.save_url,
                    data: {
                        fixedQuestions: JSON.stringify(transaction.fixedQuestions)
                    },
                    dataType: 'json',
                    success: function (data) {
                        COMMCAREHQ.app_manager.updateDOM(data.update);
                    }
                });
            }
        });

        self.validate = ko.computed(function(){
            var duplicate = _.find(_.values(self.transaction.propertyCounts()), function(count){
                return count > 1;
            });
            var isValid = duplicate === undefined;
            self.saveButton.fire(isValid ? 'enable' : 'disable');
            return  isValid;
        });

        self.change = function () {
            self.saveButton.fire('change');
        };

        self.init = function () {
            _.delay(function () {
                ko.applyBindings(self, self.home.get(0));
                self.home.on('textchange', 'input', self.change)
                     // all select2's are represented by an input[type="hidden"]
                     .on('change', 'select, input[type="hidden"]', self.change)
                     .on('click', 'a', self.change);
            });
        }
    };

    return {
        Careplan: Careplan
    };
}());

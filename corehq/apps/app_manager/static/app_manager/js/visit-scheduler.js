/*globals $, COMMCAREHQ, _, ko, CC_UTILS, console*/

var VisitScheduler = (function () {
    'use strict';

    var Scheduler = function (params) {
        var self = this;

        self.home = params.home;
        self.questions = params.questions;
        self.save_url = params.save_url;

        self.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: "You have unchanged case settings",
            save: function () {
                var schedule = JSON.stringify(FormSchedule.unwrap(self.formSchedule));
                self.saveButton.ajax({
                    type: 'post',
                    url: self.save_url,
                    data: {
                        schedule: schedule
                    },
                    dataType: 'json',
                    success: function (data) {
                        COMMCAREHQ.app_manager.updateDOM(data.update);
                    }
                });
            }
        });

        self.getQuestions = function (filter, excludeHidden, includeRepeat) {
            return CC_UTILS.getQuestions(self.questions, filter, excludeHidden, includeRepeat);
        };
        self.getAnswers = function (condition) {
            return CC_UTILS.getAnswers(self.questions, condition);
        };

        self.change = function () {
            self.saveButton.fire('change');
        };

        self.schedulePhase = SchedulePhase.wrap(params.phase, self);
        self.formSchedule = FormSchedule.wrap(params.schedule, self, self.schedulePhase);

        self.init = function () {
            _.defer(function () {
                ko.applyBindings(self, self.home.get(0));
                self.home.on('textchange', 'input', self.change)
                     // all select2's are represented by an input[type="hidden"]
                     .on('change', 'select, input[type="hidden"]', self.change)
                     .on('click', 'a:not(.header)', self.change)
                     .on('change', 'input[type="checkbox"]', self.change);

                // https://gist.github.com/mkelly12/424774/#comment-92080
                $('#visit-scheduler input').on('textchange', self.change);
            });
        };
    };

    var ScheduleRelevancy = {
        mapping: function(self){
            return {
                include: [
                    'starts',
                    'expires',
                ]
            };
        },
        wrap: function(data){
            var self = {};
            ko.mapping.fromJS(data, ScheduleRelevancy.mapping(self), self);
            self.starts_type = ko.observable(self.starts() < 0 ? 'before' : 'after');
            self.expires_type = ko.observable(self.expires() < 0 ? 'before' : 'after');
            self.enableFormExpiry = ko.observable(self.expires() !== null);
            self.starts = ko.observable(Math.abs(self.starts()));
            self.expires = ko.observable(Math.abs(self.expires()));
            return self;
        },
        unwrap: function(self){
            return ko.mapping.toJS(self, ScheduleRelevancy.mapping(self));
        }
    };

    var ScheduleVisit = {
        mapping: function (self) {
            return {
                include: [
                    'due',
                    'type',
                    'starts',
                    'expires',
                    'repeats',
                    'increment',
                ]
            };
        },
        wrap: function (data, config) {
            var self = {
                config: config
            };
            ko.mapping.fromJS(data, ScheduleVisit.mapping(self), self);
            if (self.repeats()){
                self.due(self.increment());
                self.type('repeats');
            }
            self.starts(self.starts() * -1);
            return self;
        },

        unwrap: function (self) {
            return ko.mapping.toJS(self, ScheduleVisit.mapping(self));
        }
    };

    var SchedulePhase = {
        mapping: function(self){
            return {
                include: [
                    'anchor',
                ]
            };
        },
        wrap: function (data, config) {
            var self = {};
            ko.mapping.fromJS(data, SchedulePhase.mapping(self), self);
            return self;
        }
    };

    var FormSchedule = {
        mapping: function (self) {
            return {
                include: [
                    'expires',
                    'allow_unscheduled',
                    'transition_condition',
                    'termination_condition'
                ],
                visits: {
                    create: function (options) {
                        options.data.type = options.data.due < 0 ? 'before' : 'after';
                        options.data.due = Math.abs(options.data.due);
                        return ScheduleVisit.wrap(options.data,  self);
                    }
                }
            };
        },
        wrap: function (data, config, phase) {
            var self = {
                config: config
            };
            ko.mapping.fromJS(data, FormSchedule.mapping(self), self);

            // for compatibility with common template: case-config:condition
            self.allow = {
                repeats: function () {
                    return false;
                }
            };

            self.transition = ko.computed(FormSchedule.conditionComputed(self.config, self.transition_condition));
            self.terminate = ko.computed(FormSchedule.conditionComputed(self.config, self.termination_condition));

            self.allowExpiry = ko.computed(function () {
                 return self.transition_condition.type() === 'never' &&
                     self.termination_condition.type() === 'never';
            });

            self.hasExpiry = ko.observable();

            self.hasRepeatVisit = ko.computed(function(){
                return self.visits()[self.visits().length - 1].type() === 'repeats';
            });

            self.phase = phase;

            self.relevancy = ScheduleRelevancy.wrap(data);

            self.addVisit = function () {
                self.visits.push(ScheduleVisit.wrap({
                    due: null,
                    type: 'after',
                    starts: null,
                    expires: null,
                    increment: null,
                    repeats: false
                }));
            };

            self.removeVisit = function(visit) {
                self.visits.remove(visit);
            };

            return self;
        },

        conditionComputed: function(config, condition) {
            return {
                read: function () {
                    if (condition) {
                        return condition.type() !== 'never';
                    } else {
                        return false;
                    }

                },
                write: function (value) {
                    condition.type(value ? 'always' : 'never');
                    config.saveButton.fire('change');
                }
            };
        },

        cleanCondition: function (condition) {
            if (condition.type() !== 'if') {
                condition.question(null);
                condition.answer(null);
                condition.operator(null);
            }
        },

        unwrap: function (self) {
            FormSchedule.cleanCondition(self.transition_condition);
            FormSchedule.cleanCondition(self.termination_condition);
            var schedule = ko.mapping.toJS(self, FormSchedule.mapping(self));
            schedule.starts = self.relevancy.starts() * (self.relevancy.starts_type() === 'before' ? -1 : 1);
            if (self.relevancy.enableFormExpiry() && self.allowExpiry()){
                schedule.expires = self.relevancy.expires() * (self.relevancy.expires_type() === 'before' ? -1 : 1);
            }
            else{
                schedule.expires = null;
            }

            schedule.anchor = self.phase.anchor();
            schedule.visits = _.map(schedule.visits, function(visit) {
                var due = visit.due * (visit.type === 'before' ? -1 : 1);
                var repeats = visit.type === 'repeats';
                return {
                    due: repeats ? null : due,
                    starts: visit.starts * -1,
                    expires: visit.expires,
                    repeats: repeats,
                    increment: repeats ? visit.due : null
                };
            });
            return schedule;
        }
    };

    return {
        Scheduler: Scheduler
    };
}());

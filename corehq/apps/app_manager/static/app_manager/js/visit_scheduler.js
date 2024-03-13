/*globals $, _, ko, console, hqImport */
hqDefine('app_manager/js/visit_scheduler', function () {
    'use strict';
    var app_manager = hqImport('app_manager/js/app_manager');
    var caseConfigUtils = hqImport('app_manager/js/case_config_utils');
    var moduleScheduler = function (params) {
        // Edits the schedule phases on the module setting page
        var self = {};
        self.home = params.home;

        self.init = function () {
            _.defer(function () {
                if (self.home.length) {
                    self.home.koApplyBindings(self);
                    self.home.on('textchange', 'input', self.change)
                        .on('change', 'select', self.change)
                        .on('click', 'a:not(.header)', self.change)
                        .on('change', 'input[type="checkbox"]', self.change);

                    // https://gist.github.com/mkelly12/424774/#comment-92080
                    // textchange doesn't work with live event binding
                    $('#module-scheduler input').on('textchange', self.change);
                }
            });
        };

        self.change = function () {
            self.saveButton.fire('change');
        };

        self.saveButton = hqImport("hqwebapp/js/bootstrap3/main").initSaveButton({
            unsavedMessage: "You have unchanged schedule settings",
            save: function () {
                self.saveButton.ajax({
                    type: 'post',
                    url: params.saveUrl,
                    data: {
                        phases: JSON.stringify(self.serializePhases()),
                        has_schedule: self.hasSchedule(),
                    },
                    dataType: 'json',
                    success: function (data) {
                        app_manager.updateDOM(data.update);
                    },
                });
            },
        });

        var phaseModel = function (id, anchor, forms) {
            var self = {};
            self.id = id;
            self.anchor = hqImport('hqwebapp/js/bootstrap3/ui-element').select(params.caseProperties).val(anchor);
            self.anchor.observableVal = ko.observable(self.anchor.val());
            self.anchor.on("change", function () {
                self.anchor.observableVal(self.anchor.val());
            });
            hqImport('app_manager/js/details/utils').setUpAutocomplete(self.anchor, params.caseProperties);
            self.forms = ko.observable(forms);
            self.form_abbreviations = ko.computed(function () {
                return _.map(self.forms(), function (form) {
                    return form === '' ? '(no abbreviation)' : form;
                }).join(', ');
            });
            return self;
        };

        self.hasSchedule = ko.observable(params.hasSchedule);

        self.phases = ko.observableArray(
            _.map(params.schedulePhases, function (phase) {
                return phaseModel(phase.id, phase.anchor, phase.forms);
            })
        );
        self.phases.subscribe(function (phase) {
            self.change();
        });

        self.selectedPhase = ko.observable();
        self.selectPhase = function (phase) {
            self.selectedPhase(phase);
        };

        self.addPhase = function () {
            var NEW_PHASE_ID = -1;
            self.phases.push(phaseModel(NEW_PHASE_ID, "", []));
        };

        self.removePhase = function (phase) {
            self.phases.remove(phase);
        };

        self.serializePhases = function () {
            return _.map(self.phases(), function (phase) {
                return {
                    id: phase.id,
                    anchor: phase.anchor.val(),
                };
            });
        };

        return self;
    };

    var schedulerModel = function (params) {
        var self = {};

        self.home = params.home;
        self.questions = params.questions;
        self.save_url = params.save_url;

        self.saveButton = hqImport("hqwebapp/js/bootstrap3/main").initSaveButton({
            unsavedMessage: "You have unsaved schedule settings",
            save: function () {
                var isValid = self.validate();
                if (isValid) {
                    var schedule = JSON.stringify(formSchedule.unwrap(self.formSchedule));
                    self.saveButton.ajax({
                        type: 'post',
                        url: self.save_url,
                        data: {
                            schedule: schedule,
                        },
                        dataType: 'json',
                        success: function (data) {
                            app_manager.updateDOM(data.update);
                        },
                    });
                }
            },
        });

        self.getQuestions = function (filter, excludeHidden, includeRepeat) {
            return caseConfigUtils.getQuestions(self.questions, filter, excludeHidden, includeRepeat);
        };
        self.getAnswers = function (condition) {
            return caseConfigUtils.getAnswers(self.questions, condition);
        };

        self.change = function () {
            self.saveButton.fire('change');
        };

        self.validate = function () {
            var errors = 0;
            var $add_visit_button = self.home.find("#add-visit");

            if (self.formSchedule.visits().length === 0) {
                $add_visit_button.closest(".form-group").addClass("has-error");
                $add_visit_button.siblings(".error-text").show();
                errors += 1;
            } else {
                $add_visit_button.closest(".form-group").removeClass("has-error");
                $add_visit_button.siblings(".error-text").hide();
            }

            var required = self.home.find(":required").not(":disabled");
            required.each(function (i, req) {
                var $req = $(req);
                if ($req.val().trim().length === 0) {
                    $req.closest(".form-group").addClass("has-error");
                    $req.siblings(".error-text").show();
                    errors += 1;
                } else {
                    $req.closest(".form-group").removeClass("has-error");
                    $req.siblings(".error-text").hide();
                }
            });

            if (!self.formSchedule.scheduleEnabled() || !errors) {
                self.home.find("#form-errors").hide();
                return true;
            } else {
                self.home.find("#form-errors").show();
                return false;
            }
        };

        self.schedulePhase = schedulePhase.wrap(params.phase, self);
        self.formSchedule = formSchedule.wrap(params, self, self.schedulePhase);

        self.init = function () {
            _.defer(function () {
                self.home.koApplyBindings(self);
                self.home.on('textchange', 'input', self.change)
                    .on('change', 'select', self.change)
                    .on('click', 'a:not(.header)', self.change)
                    .on('change', 'input[type="checkbox"]', self.change);

                self.applyGlobalEventHandlers();
            });
        };

        self.applyGlobalEventHandlers = function () {
            // https://gist.github.com/mkelly12/424774/#comment-92080
            // textchange doesn't work with live event binding
            $('#visit-scheduler input').on('textchange', self.change);
        };

        return self;
    };

    var scheduleRelevancy = {
        mapping: function (self) {
            return {
                include: [
                    'starts',
                    'expires',
                ],
            };
        },
        wrap: function (data) {
            var self = {};
            ko.mapping.fromJS(data, scheduleRelevancy.mapping(self), self);
            self.starts_type = ko.observable(self.starts() < 0 ? 'before' : 'after');
            self.expires_type = ko.observable(self.expires() < 0 ? 'before' : 'after');
            self.enableFormExpiry = ko.observable(self.expires() !== null);
            self.starts = ko.observable(Math.abs(self.starts()));
            self.expires = ko.observable(Math.abs(self.expires()));
            return self;
        },
        unwrap: function (self) {
            return ko.mapping.toJS(self, scheduleRelevancy.mapping(self));
        },
    };

    var scheduleVisit = {
        mapping: function (self) {
            return {
                include: [
                    'due',
                    'type',
                    'starts',
                    'expires',
                    'repeats',
                    'increment',
                ],
            };
        },
        wrap: function (data, config) {
            var self = {
                config: config,
            };
            ko.mapping.fromJS(data, scheduleVisit.mapping(self), self);
            if (self.repeats()) {
                self.due(self.increment());
                self.type('repeats');
            }
            self.starts(self.starts() * -1);
            return self;
        },

        unwrap: function (self) {
            return ko.mapping.toJS(self, scheduleVisit.mapping(self));
        },
    };

    var schedulePhase = {
        mapping: function (self) {
            return {
                include: [
                    'anchor',
                ],
            };
        },
        wrap: function (data, config) {
            var self = {};
            ko.mapping.fromJS(data, schedulePhase.mapping(self), self);
            return self;
        },
    };

    var formSchedule = {
        mapping: function (self) {
            return {
                include: [
                    'expires',
                    'allow_unscheduled',
                    'transition_condition',
                    'termination_condition',
                    'schedule_form_id',
                ],
                visits: {
                    create: function (options) {
                        options.data.type = options.data.due < 0 ? 'before' : 'after';
                        options.data.due = Math.abs(options.data.due);
                        return scheduleVisit.wrap(options.data, self);
                    },
                },
            };
        },
        wrap: function (data, config, phase) {
            var self = {
                config: config,
                all_schedule_phase_anchors: data.all_schedule_phase_anchors,
                phase: phase,
            };
            ko.mapping.fromJS(data.schedule, formSchedule.mapping(self), self);

            // for compatibility with common template: case-config:condition
            self.allow = {
                repeats: function () {
                    return false;
                },
            };

            self.scheduleEnabled = ko.observable(data.schedule.enabled);
            self.transition = ko.computed(formSchedule.conditionComputed(self.config, self.transition_condition));
            self.terminate = ko.computed(formSchedule.conditionComputed(self.config, self.termination_condition));

            self.allowExpiry = ko.computed(function () {
                return self.transition_condition.type() === 'never' &&
                    self.termination_condition.type() === 'never';
            });

            self.hasExpiry = ko.observable();

            self.hasRepeatVisit = ko.computed(function () {
                return self.visits().length > 0 && self.visits()[self.visits().length - 1].type() === 'repeats';
            });

            self.relevancy = scheduleRelevancy.wrap(data.schedule);
            var xmlRe = /\s+|<+|>+|&+|"+|'+/g;
            self.schedule_form_id = ko.observable(data.schedule_form_id || '').snakeCase(xmlRe);

            self.addVisit = function () {
                self.visits.push(scheduleVisit.wrap({
                    due: null,
                    type: 'after',
                    starts: null,
                    expires: null,
                    increment: null,
                    repeats: false,
                }));
            };

            self.removeVisit = function (visit) {
                self.visits.remove(visit);
            };

            return self;
        },

        conditionComputed: function (config, condition) {
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
                },
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
            formSchedule.cleanCondition(self.transition_condition);
            formSchedule.cleanCondition(self.termination_condition);
            var schedule = ko.mapping.toJS(self, formSchedule.mapping(self));
            schedule.enabled = self.scheduleEnabled();
            schedule.starts = self.relevancy.starts() * (self.relevancy.starts_type() === 'before' ? -1 : 1);
            if (self.relevancy.enableFormExpiry() && self.allowExpiry()) {
                schedule.expires = self.relevancy.expires() * (self.relevancy.expires_type() === 'before' ? -1 : 1);
            } else {
                schedule.expires = null;
            }

            schedule.anchor = self.phase.anchor() || '';
            schedule.schedule_form_id = self.schedule_form_id();
            schedule.visits = _.map(schedule.visits, function (visit) {
                var due = visit.due * (visit.type === 'before' ? -1 : 1);
                var repeats = visit.type === 'repeats';
                return {
                    due: repeats ? null : due,
                    starts: visit.starts * -1,
                    expires: visit.expires,
                    repeats: repeats,
                    increment: repeats ? visit.due : null,
                };
            });
            return schedule;
        },
    };

    return {
        schedulerModel: schedulerModel,
        moduleScheduler: moduleScheduler,
    };
});

// Verbatim from http://www.knockmeout.net/2011/05/dragging-dropping-and-sorting-with.html
//control visibility, give element focus, and select the contents (in order)
ko.bindingHandlers.visibleAndSelect = {
    update: function (element, valueAccessor) {
        ko.bindingHandlers.visible.update(element, valueAccessor);
        if (valueAccessor()) {
            _.defer(function () {
                $(element).focus().select();
            });
        }
    },
};

hqDefine("app_manager/js/details/case_list_callout", function () {
    var caseListLookupViewModel = function ($el, state, lang, saveButton) {
        'use strict';
        var self = {};
        var detailType = $el.data('detail-type');

        var observableKeyValue = function (obs) {
            var self = {};
            self.key = ko.observable(obs.key);
            self.value = ko.observable(obs.value);
            return self;
        };

        var _fireChange = function () {
            saveButton.fire('change');
        };

        self.initSaveButtonListeners = function ($el) {
            $el.find('input[type=text], textarea').on('textchange', _fireChange);
            $el.find('input[type=checkbox]').on('change', _fireChange);
            $el.find(".case-list-lookup-icon button").on("click", _fireChange); // Trigger save button when icon upload buttons are clicked
        };

        var _removeEmpty = function (type) {
            self[type].remove(function (t) {
                return (!t.key() && !t.value());
            });
        };

        self.addItem = function (type) {
            _removeEmpty(type);
            var data = (type === 'extras') ? {key: '', value: ''} : {key: ''};
            self[type].push(observableKeyValue(data));
        };

        self.removeItem = function (type, item) {
            self[type].remove(item);
            if (self[type]().length === 0) {
                self.addItem(type);
            }
            _fireChange();
        };

        var _trimmedExtras = function () {
            return _.compact(_.map(self.extras(), function (extra) {
                if (!(extra.key() === "" && extra.value() === "")) {
                    return {key: extra.key(), value: extra.value()};
                }
            }));
        };

        var _trimmedResponses = function () {
            return _.compact(_.map(self.responses(), function (response) {
                if (response.key() !== "") {
                    return {key: response.key()};
                }
            }));
        };

        self.serialize = function () {
            var imagePath = $el.find(".case-list-lookup-icon input[type=hidden]").val() || null;

            return {
                lookup_enabled: self.lookup_enabled(),
                lookup_autolaunch: self.lookup_autolaunch(),
                lookup_action: self.lookup_action(),
                lookup_name: self.lookup_name(),
                lookup_extras: _trimmedExtras(),
                lookup_responses: _trimmedResponses(),
                lookup_image: imagePath,
                lookup_display_results: self.lookup_display_results(),
                lookup_field_header: self.lookup_field_header.val(),
                lookup_field_template: self.lookup_field_template(),
            };
        };

        var _validateInputs = function (errors) {
            errors = errors || [];
            $el.find('input[required]').each(function () {
                var $this = $(this);
                if ($this.val().trim().length === 0) {
                    $this.closest('.form-group').addClass('has-error');
                    var $help = $this.siblings('.help-block');
                    $help.show();
                    errors.push($help.text());
                }
                else {
                    $this.closest('.form-group').removeClass('has-error');
                    $this.siblings('.help-block').hide();
                }
            });
            return errors;
        };

        var _validateExtras = function (errors) {
            errors = errors || [];
            var $extras = $el.find("." + detailType + "-extras"),
                $extra_help = $extras.find(".help-block");

            if (!_trimmedExtras().length) {
                $extras.addClass('has-error');
                $extra_help.show();
                errors.push($extra_help.text());
            }
            else {
                $extras.removeClass('has-error');
                $extra_help.hide();
            }
            return errors;
        };

        var _validate_responses = function (errors) {
            errors = errors || [];
            var $responses = $el.find("." + detailType + "-responses"),
                $responseHelp = $responses.find(".help-block");

            if (!_trimmedResponses().length) {
                $responses.addClass('has-error');
                $responseHelp.show();
                errors.push($responseHelp.text());
            }
            else {
                $responses.removeClass('has-error');
                $responseHelp.hide();
            }
            return errors;
        };

        self.validate = function () {
            var errors = [];

            $("#message-alerts > div").each(function () {
                $(this).alert('close');
            });

            if (self.lookup_enabled()) {
                _validateInputs(errors);
                _validateExtras(errors);
                _validate_responses(errors);
            }

            if (errors.length) {
                var alert_user = hqImport("hqwebapp/js/bootstrap3/alert_user").alert_user;
                _.each(errors, function (error) {
                    alert_user(error, "danger");
                });
                return false;
            }
            return true;
        };

        self.$el = $el;
        self.$form = $el.find('form');

        self.lookup_enabled = ko.observable(state.lookup_enabled);
        self.lookup_autolaunch = ko.observable(state.lookup_autolaunch);
        self.lookup_action = ko.observable(state.lookup_action);
        self.lookup_name = ko.observable(state.lookup_name);
        self.extras = ko.observableArray(ko.utils.arrayMap(state.lookup_extras, function (extra) {
            return observableKeyValue(extra);
        }));
        self.responses = ko.observableArray(ko.utils.arrayMap(state.lookup_responses, function (response) {
            return observableKeyValue(response);
        }));

        if (self.extras().length === 0) {
            self.addItem('extras');
        }
        if (self.responses().length === 0) {
            self.addItem('responses');
        }

        self.lookup_display_results = ko.observable(state.lookup_display_results);
        var invisible = "", visible = "";
        if (state.lookup_field_header[lang]) {
            visible = invisible = state.lookup_field_header[lang];
        } else {
            _.each(_.keys(state.lookup_field_header), function (lang) {
                if (state.lookup_field_header[lang]) {
                    visible = state.lookup_field_header[lang]
                        + hqImport('hqwebapp/js/ui_elements/ui-element-langcode-button').LANG_DELIN
                        + lang;
                }
            });
        }

        self.lookup_field_header = hqImport('hqwebapp/js/bootstrap3/ui-element').input().val(invisible);
        self.lookup_field_header.setVisibleValue(visible);
        self.lookup_field_header.observableVal = ko.observable(self.lookup_field_header.val());
        self.lookup_field_header.on('change', function () {
            self.lookup_field_header.observableVal(self.lookup_field_header.val());
            _fireChange();  // input node created too late for initSaveButtonListeners
        });
        self.lookup_field_template = ko.observable(state.lookup_field_template || '@case_id');

        self.show_add_extra = ko.computed(function () {
            if (self.extras().length) {
                var last_key = self.extras()[self.extras().length - 1].key(),
                    last_value = self.extras()[self.extras().length - 1].value();
                return !(last_key === "" && last_value === "");
            }
            return true;
        });

        self.show_add_response = ko.computed(function () {
            if (self.responses().length) {
                var last_key = self.responses()[self.responses().length - 1].key();
                return last_key !== "";
            }
            return true;
        });

        self.initSaveButtonListeners(self.$el);

        return self;
    };

    var createCaseListLookupViewModel = function ($el, state, lang, saveButton) {
        return caseListLookupViewModel($el, state, lang, saveButton);
    };

    return {
        caseListLookupViewModel: createCaseListLookupViewModel,
    };
});

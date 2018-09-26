hqDefine("hqwebapp/js/select2_handler_v4", [
    "jquery",
    "knockout",
    "underscore",
    "select2/dist/js/select2.full.min",
    "bootstrap-timepicker/js/bootstrap-timepicker",
], function (
    $,
    ko,
    _
) {
    var baseSelect2Handler = function (options) {
        // For use with BaseAsyncHandler
        // todo: documentation (biyeun)
        'use strict';
        var self = {};
        self.fieldName = options.fieldName;
        self.placeholder = options.placeholder;
        self.multiple = options.multiple || false;
        self.value = ko.observable();
        self.createTags = options.createTags || false;
        self.clear = function () {
            var fieldInput = self.utils.getField();
            fieldInput.val("").trigger("change");
        };

        self.getHandlerSlug = function () {
            // This is the slug for the AsyncHandler you'll be using on the server side
            throw new Error('getHandlerSlug must be implemented');
        };

        self.getExtraData = function () {
            return {};
        };

        self.processResults = function (response) {
            // override this if you want to do something special with the response.
            return response;
        };

        self.createNewChoice = function (term, selectedData) {
            // override this if you want the search to return the option of creating whatever
            // the user entered.
        };

        self.templateResult = function (result) {

            return result.text;
        };

        self.templateSelection = function (result) {
            return result.text;
        };

        self.getInitialData = function (element) {
            // override this if you want to format the value that is initially stored in the field for this widget.
        };

        self.utils = {
            getField: function () {
                return $('[name="' + self.fieldName + '"]');
            },
        };

        self.init = function () {
            var fieldInput = self.utils.getField();

            fieldInput.select2(_.extend({
                multiple: true,
                tags: fieldInput.data("choices"),
            }, {}));

            fieldInput.select2({
                minimumInputLength: 0,
                allowClear: true,
                multiple: self.multiple,
                placeholder: self.placeholder,
                ajax: {
                    delay: 150,
                    url: '',
                    dataType: 'json',
                    type: 'post',
                    data: function (term) {
                        var data = self.getExtraData(term);
                        data['handler'] = self.getHandlerSlug();
                        data['action'] = self.fieldName;
                        data['searchString'] = term;
                        return data;
                    },
                    processResults: self.processResults,

                },
                tags: self.createTags,
                createTag: self.createNewChoice,
                templateResult: self.templateResult,
                templateSelection: self.templateSelection,

            });

            var initial = self.getInitialData(fieldInput);
            if (initial) {
                if (!_.isArray(initial)) {
                    initial = [initial];
                }
                _.each(initial, function (result) {
                    fieldInput.append(new Option(result.text, result.id));
                });
                fieldInput.val(_.pluck(initial, 'id')).trigger('change');
            }

            if (self.onSelect2Change) {
                fieldInput.on("change", self.onSelect2Change);
            }


        };

        return self;
    };

    return {
        baseSelect2Handler: baseSelect2Handler,
    };
});

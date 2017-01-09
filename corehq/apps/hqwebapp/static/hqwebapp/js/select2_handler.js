var BaseSelect2Handler = function (options) {
    // For use with BaseAsyncHandler
    // todo: documentation (biyeun)
    'use strict';
    var self = this;
    self.currentValue = options.currentValue;
    self.fieldName = options.fieldName;
    self.value = ko.observable();

    self.clear = function () {
        var fieldInput = self.utils.getField();
        fieldInput.select2('val', '');
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

    self.formatResult = function (result) {
        return result.text;
    };

    self.formatSelection = function (result) {
        return result.text;
    };

    self.getInitialData = function (element) {
        // override this if you want to format the value that is initially stored in the field for this widget.
    };

    self.utils = {
        getField: function () {
            return $('[name="' + self.fieldName + '"]');
        }
    };

    self.init = function () {
        var fieldInput = self.utils.getField();
        fieldInput.select2({
            minimumInputLength: 0,
            allowClear: true,
            ajax: {
                quietMillis: 150,
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
                results: self.processResults,
                500: function () {
                    self.error(
                        gettext("There was an issue communicating with the server. Please try back later.")
                    );
                }
            },
            createSearchChoice: self.createNewChoice,
            formatResult: self.formatResult,
            formatSelection: self.formatSelection,
            initSelection : function (element, callback) {
                if (element.val()) {
                    var data = self.getInitialData(element);
                    if (data) callback(data);
                }
            }
        });
        if (self.onSelect2Change) {
            fieldInput.on("change", self.onSelect2Change);
        }
    };
};

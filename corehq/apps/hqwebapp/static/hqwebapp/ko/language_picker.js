var LanguagePickerViewModel = function (onSuccessFn) {
    'use strict';
    var self = this;

    self.langcode = ko.observable();
    self.onSuccess = onSuccessFn;

    self.init = function () {
          $('#language-picker-input').select2({
                placeholder: 'Language Name or Code',
                minimumInputLength: 0,
                allowClear: true,
                ajax: {
                    quietMillis: 150,
                    url: '/langcodes/langs.json',
                    dataType: 'json',
                    data: function (term) {
                        return {
                            term: term.toLowerCase()
                        };
                    },
                    results: function (data) {
                        return {
                            results: _.map(data, function (res) {
                                return {
                                    id: res.code,
                                    text: res.code + " (" + res.name + ")"
                                };
                            })
                        };
                    }
                }
          });
    };

    self.confirmLanguageChoice = function () {
        if (self.langcode()) {
            self.onSuccess(self.langcode());
        }
    };
};

$.fn.languagePicker = function (onSuccessFn) {
    this.each(function (i) {
        var viewModel = new LanguagePickerViewModel(onSuccessFn);
        $(this).koApplyBindings(viewModel);
        viewModel.init();
    })
};

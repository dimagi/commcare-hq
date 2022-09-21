hqDefine('generic_inbound/js/api_edit', [
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'generic_inbound/js/copy_data',
], function (_, ko, initialPageData) {

    let ValidationModel = function (data) {
        let self = ko.mapping.fromJS(data);

        self.nameError = ko.computed(() => {
            return self.name().length === 0 || self.name().length > 64;
        });

        self.expressionError = ko.computed(() => {
            return self.expression_id() === null;
        });

        self.messageError = ko.computed(() => {
            return self.message().length === 0;
        });

        self.isValid = ko.computed(() => {
            return !self.nameError() && !self.expressionError() && !self.messageError();
        });
        return self;
    };

    let ViewModel = function (validations) {
        let self = {};

        self.filters = initialPageData.get("filters");
        self.validations = ko.observableArray(validations.map(ValidationModel));
        self.initialValidationCount = validations.length;

        self.addValidation = function () {
            self.validations.push(
                ValidationModel({"name": "", "expression_id": null, "message": "", "id": null})
            );
        };

        self.enableSubmit = ko.computed(() => {
            return self.validations().filter((v) => !v.isValid()).length === 0;
        });

        self.validateForm = function () {
            return self.enableSubmit();
        };

        return self;
    };

    $(function () {
        $("#edit-api").koApplyBindings(ViewModel(
            initialPageData.get("validations")
        ));
    });
});

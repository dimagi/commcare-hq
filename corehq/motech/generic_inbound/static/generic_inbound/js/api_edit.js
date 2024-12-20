hqDefine('generic_inbound/js/api_edit', [
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'generic_inbound/js/manage_links',
    'generic_inbound/js/copy_data',
    'commcarehq',
], function (_, ko, initialPageData, manageLinks) {

    const VALIDATION_DEFAULTS = {
        "name": "", "expression_id": null, "message": "", "id": null, "toDelete": false,
    };

    let ValidationModel = function (data) {
        data = _.defaults(data, VALIDATION_DEFAULTS);
        let self = ko.mapping.fromJS(data);
        self.nameError = ko.computed(() => {
            return self.name().length === 0 || self.name().length > 64;
        });

        self.expressionError = ko.computed(() => {
            return self.expression_id() === null;
        });

        self.editUrl = ko.computed(() => {
            return manageLinks.getExpressionUrl(self.expression_id());
        });

        self.messageError = ko.computed(() => {
            return self.message().length === 0;
        });

        self.isValid = ko.computed(() => {
            return !self.nameError() && !self.expressionError() && !self.messageError();
        });
        return self;
    };

    let SubModelWrapper = function (modeClass, data, newDefautls) {
        let self = {};
        self.models = ko.observableArray(data.map(modeClass));
        self.initialCount = data.length;
        self.total = ko.computed(() => {
            return self.models().length;
        });
        self.add = function () {
            self.models.push(modeClass(newDefautls));
        };
        self.remove = function (item) {
            self.models.remove(item);
        };
        self.allValid = ko.computed(() => {
            return self.models().filter((v) => !v.isValid()).length === 0;
        });
        return self;
    };

    let ViewModel = function (validations) {
        let self = {};

        self.filters = initialPageData.get("filters");
        self.validations = SubModelWrapper(ValidationModel, validations, VALIDATION_DEFAULTS);

        self.validateForm = function () {
            return self.validations.allValid();
        };

        return self;
    };

    $(function () {
        $("#edit-api").koApplyBindings(ViewModel(
            initialPageData.get("validations")
        ));
    });
});

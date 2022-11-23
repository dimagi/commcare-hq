hqDefine('generic_inbound/js/api_edit', [
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'generic_inbound/js/copy_data',
], function (_, ko, initialPageData) {

    const VALIDATION_DEFAULTS = {
        "name": "", "expression_id": null, "message": "", "id": null, "toDelete": false,
    };

    const getExpressionUrl = function (expressionId) {
        if (expressionId) {
            return initialPageData.reverse('edit_ucr_expression', expressionId);
        } else {
            return initialPageData.reverse('ucr_expressions');
        }
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
            return getExpressionUrl(self.expression_id());
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

        // update the links based on selection
        const filterLinkEl = $('#div_id_filter_expression .input-group-addon a');
        const transformLinkEl = $('#div_id_transform_expression .input-group-addon a');
        const filterSelect = $('#id_filter_expression');
        const transformSelect = $('#id_transform_expression');

        const updateLink = function (selectEl, element) {
            let optionSelected = selectEl.find("option:selected");
            element.attr('href', getExpressionUrl(optionSelected.val()));
        };

        filterSelect.change(function () {
            updateLink($(this), filterLinkEl);
        });

        transformSelect.change(function () {
            updateLink($(this), transformLinkEl);
        });

        // update based on initial values
        updateLink(filterSelect, filterLinkEl);
        updateLink(transformSelect, transformLinkEl);

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

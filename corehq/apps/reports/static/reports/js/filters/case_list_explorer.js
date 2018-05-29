var SuggestedCaseTypes = function(){
    // Adds the required properties to filter the case type autocomplete dropdowns
    var self = this;
    self.currentCaseType = ko.observable('');
    $('#report_filter_case_type').on('change', function(e){
        self.currentCaseType(e.val);
    });

    self.suggestedProperties = ko.computed(function(){
        if (self.currentCaseType() === ''){
            return self.allCaseProperties;
        }
        return _.filter(self.allCaseProperties, function(prop){
            return prop['case_type'] === self.currentCaseType() || prop['case_type'] === null;
        });
    });
};

hqDefine("reports/js/filters/case_search_xpath", function() {
    var CaseSearchXpathViewModel = function(allCaseProperties){
        var self = this;
        self.allCaseProperties = allCaseProperties;
        SuggestedCaseTypes.apply(self);
        return self;
    };

    return {model: CaseSearchXpathViewModel};
});


ko.bindingHandlers.xPathAutocomplete = {
    init: function(element) {
        var $element = $(element);
        if (!$element.atwho) {
            throw new Error("The typeahead binding requires Atwho.js and Caret.js");
        }

        hqImport('hqwebapp/js/atwho').init($element, {
            atwhoOptions: {
                displayTpl: '<li><span class="label label-default">${case_type}</span> ${name}</li>',
                callbacks: {},
            },
            afterInsert: function() {
                $element.trigger('textchange');
            },
            replaceValue: false,
        });

        $element.on("textchange", function() {
            if ($element.val()) {
                $element.change();
            }
        });
    },

    update: function(element, valueAccessor) {
        $(element).atwho('load', '', ko.utils.unwrapObservable(valueAccessor()));
    },
};

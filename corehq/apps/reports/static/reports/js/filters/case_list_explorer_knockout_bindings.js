ko.bindingHandlers.xPathAutocomplete = {
    init: function(element) {
        var $element = $(element);
        if (!$element.atwho) {
            throw new Error("The typeahead binding requires Atwho.js and Caret.js");
        }

        hqImport('hqwebapp/js/atwho').init($element, {
            atwhoOptions: {
                displayTpl: function(item){
                    if (item.case_type){
                        return '<li><span class="label label-default">${case_type}</span> ${name}</li>';
                    }
                    var labelClass = item.meta_type === 'info' ? 'label-primary' : 'label-info';
                    return '<li><span class="label ' + labelClass +'">${meta_type}</span> ${name}</li>';
                },
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


ko.bindingHandlers.explorerColumnsAutocomplete = {
    init: function(element) {
        var $element = $(element);
        if (!$element.atwho) {
            throw new Error("The typeahead binding requires Atwho.js and Caret.js");
        }

        hqImport('hqwebapp/js/atwho').init($element, {
            atwhoOptions: {
                displayTpl: function(item){
                    if (item.case_type){
                        return '<li><span class="label label-default">${case_type}</span> ${name}</li>';
                    }
                    return '<li><span class="label label-primary">${meta_type}</span> ${name}</li>';
                },
            },
            afterInsert: function() {
                $element.trigger('textchange');
            },
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

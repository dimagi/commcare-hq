
$(function() {
    var model = new CommtrackSettingsViewModel();
    $('#settings').submit(function() {
        return model.presubmit();
    });

    model.load(settings);
    ko.applyBindings(model);
});

function CommtrackSettingsViewModel() {
    this.source_config = ko.observable();

    this.json_payload = ko.observable();

    this.load = function(data) {
        this.source_config(new SourceConfigModel(data.source_config));
    };

    var settings = this;

    this.presubmit = function() {
        payload = this.to_json();
        this.json_payload(JSON.stringify(payload));
    };

    this.to_json = function() {
        return {
            source_config: this.source_config().to_json()
        };
    };
}

function SourceConfigModel(data) {
    this.enabled = ko.observable(data.enabled);
    this.url = ko.observable(data.url);
    this.username = ko.observable(data.username);
    this.password = ko.observable(data.password);
    this.using_requisitions = ko.observable(data.using_requisitions);

    this.to_json = function() {
        return {
            enabled: this.enabled(),
            url: this.url(),
            username: this.username(),
            password: this.password(),
            using_requisitions: this.using_requisitions()
        };
    };
}



// TODO move to shared library
ko.bindingHandlers.bind_element = {
    init: function(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
        var field = valueAccessor() || '$e';
        if (viewModel[field]) {
            console.log('warning: element already bound');
            return;
        }
        viewModel[field] = element;
        if (viewModel.onBind) {
            viewModel.onBind(bindingContext);
        }
    }
};


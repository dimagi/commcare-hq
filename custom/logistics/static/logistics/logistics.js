
$(function() {
    var model = new CommtrackSettingsViewModel();
    $('#settings').submit(function() {
        return model.presubmit();
    });

    model.load(settings);
    $("#settings").koApplyBindings(model);
});

function CommtrackSettingsViewModel() {
    this.source_config = ko.observable();

    this.json_payload = ko.observable();

    this.load = function(data) {
        this.source_config(new SourceConfigModel(data.source_config));
    };

    var settings = this;

    this.presubmit = function() {
        var payload = this.to_json();
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
    this.steady_sync = ko.observable(data.steady_sync);
    this.all_stock_data = ko.observable(data.all_stock_data);

    this.to_json = function() {
        return {
            enabled: this.enabled(),
            url: this.url(),
            username: this.username(),
            password: this.password(),
            steady_sync: this.steady_sync(),
            all_stock_data: this.all_stock_data()
        };
    };
}

function CustomField (field) {
    var self = this;
    self.label = ko.observable(field.label);
    self.isRequired = ko.observable(field.isRequired);
}


function CustomFieldsModel () {
    var self = this;
    self.customFields = ko.observableArray([]);

    self.addField = function () {
        self.customFields.push(new CustomField('', false));
    }

    self.removeField = function(field) {
        self.customFields.remove(field)
    }

    self.init = function (initialFields) {
        _.each(initialFields, function (field) {
            console.log(field.label);
            console.log(field.isRequired);
            self.customFields.push(new CustomField(field));
        });
    }
}


function submitCustomFields (url, params) {
    var $form = $("<form>")
        .attr("method", "post")
        .attr("action", url);
    $.each(params, function (name, value) {
        $("<input type='hidden'>")
            .attr("name", name)
            .attr("value", value)
            .appendTo($form);
    });
    $form.appendTo("body");
    $form.submit();
}


$('#submit-menu-form').click(function(e) {
    e.preventDefault();
    var response = postGo(
        $('#menu-form')[0].action,
        {'doc': JSON.stringify(outputJSON(buildsMenu))}
    );
});

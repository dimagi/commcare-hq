function CustomField (field) {
    var self = this;
    self.slug = ko.observable(field.slug);
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
            self.customFields.push(new CustomField(field));
        });
    }

    self.serialize = function () {
        var fields = [];
        _.each(self.customFields(), function (field) {
            fields.push({
                'slug': field.slug(),
                'label': field.label(),
                'isRequired': field.isRequired(),
            });
        });
        return fields;
    }

    self.submitFields = function (fieldsForm) {
        var customFieldsForm = $("<form>")
            .attr("method", "post")
            .attr("action", fieldsForm.action);
        $('<input type="hidden">')
            .attr('name', 'customFields')
            .attr('value', JSON.stringify(self.serialize()))
            .appendTo(customFieldsForm);
        customFieldsForm.appendTo("body");
        customFieldsForm.submit();
    }

}




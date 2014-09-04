function CustomField (field) {
    var self = this;
    self.slug = ko.observable(field.slug);
    self.label = ko.observable(field.label);
    self.is_required = ko.observable(field.is_required);
}


function CustomFieldsModel () {
    var self = this;
    self.data_fields = ko.observableArray([]);

    self.addField = function () {
        self.data_fields.push(new CustomField('', false));
    }

    self.removeField = function(field) {
        self.data_fields.remove(field)
    }

    self.init = function (initialFields) {
        _.each(initialFields, function (field) {
            self.data_fields.push(new CustomField(field));
        });
    }

    self.serialize = function () {
        var fields = [];
        _.each(self.data_fields(), function (field) {
            fields.push({
                'slug': field.slug(),
                'label': field.label(),
                'is_required': field.is_required(),
            });
        });
        return fields;
    }

    self.submitFields = function (fieldsForm) {
        var customDataFieldsForm = $("<form>")
            .attr("method", "post")
            .attr("action", fieldsForm.action);
        $('<input type="hidden">')
            .attr('name', 'data_fields')
            .attr('value', JSON.stringify(self.serialize()))
            .appendTo(customDataFieldsForm);
        customDataFieldsForm.appendTo("body");
        customDataFieldsForm.submit();
    }

}




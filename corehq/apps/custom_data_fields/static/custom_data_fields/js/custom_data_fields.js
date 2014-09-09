function CustomDataField (field) {
    var self = this;
    self.slug = ko.observable(field.slug);
    self.label = ko.observable(field.label);
    self.is_required = ko.observable(field.is_required);
}


function CustomDataFieldsModel () {
    var self = this;
    self.data_fields = ko.observableArray();

    self.addField = function () {
        self.data_fields.push(new CustomDataField('', false));
    }

    self.removeField = function (field) {
        self.data_fields.remove(field)
    }

    self.init = function (initialFields) {
        _.each(initialFields, function (field) {
            self.data_fields.push(new CustomDataField(field));
        });
    }

    self.serialize = function () {
        var fields = [];
        var fieldsToRemove = [];
        _.each(self.data_fields(), function (field) {
            if(field.slug() || field.label()) {
                fields.push({
                    'slug': field.slug(),
                    'label': field.label(),
                    'is_required': field.is_required(),
                });
            } else {
                fieldsToRemove.push(field);
            }
        });

        _.each(fieldsToRemove, function (field) {
            self.removeField(field);
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




function Choice (choice) {
    var self = this;
    self.value = ko.observable(choice);
}


function CustomDataField () {
    var self = this;
    self.slug = ko.observable();
    self.label = ko.observable();
    self.is_required = ko.observable();
    self.choices = ko.observableArray();
    self.multipleChoice = ko.observable();

    self.addChoice = function () {
        self.choices.push(new Choice());
    };

    self.removeChoice = function (choice) {
        self.choices.remove(choice);
    };

    self.init = function (field) {
        self.slug(field.slug);
        self.label(field.label);
        self.is_required(field.is_required);
        self.choices(field.choices.map(function (choice) {
            return new Choice(choice);
        }));
        self.multipleChoice(field.is_multiple_choice);
    };

    self.serialize = function () {
        var choices = [];
        var choicesToRemove = [];
        _.each(self.choices(), function (choice) {
            if (choice.value()) {
                choices.push(choice.value());
            } else {
                choicesToRemove.push(choice);
            }
        });
        _.each(choicesToRemove, function (choice) {
            self.removeChoice(choice);
        });

        return {
            'slug': self.slug(),
            'label': self.label(),
            'is_required': self.is_required(),
            'choices': choices,
            'is_multiple_choice': self.multipleChoice()
        };
    };
}


function CustomDataFieldsModel () {
    var self = this;
    self.data_fields = ko.observableArray();

    self.addField = function () {
        self.data_fields.push(new CustomDataField());
    };

    self.removeField = function (field) {
        self.data_fields.remove(field);
    };

    // Manually remove modal backrop because it is not part of the div
    // we delete otherwise
    self.removeFieldAndModal = function (field) {
        self.removeField(field);
        $(".modal-backdrop").remove();
    };

    self.init = function (initialFields) {
        _.each(initialFields, function (field) {
            custom_field = new CustomDataField();
            custom_field.init(field);
            self.data_fields.push(custom_field);
            custom_field.choices.subscribe(function() {
                $("#save-custom-fields").prop("disabled", false);
            });
        });
    };

    self.serialize = function () {
        var fields = [];
        var fieldsToRemove = [];
        _.each(self.data_fields(), function (field) {
            if(field.slug() || field.label()) {
                fields.push(field.serialize());
            } else {
                fieldsToRemove.push(field);
            }
        });

        _.each(fieldsToRemove, function (field) {
            self.removeField(field);
        });
        return fields;
    };

    self.submitFields = function (fieldsForm) {
        var customDataFieldsForm = $("<form>")
            .attr("method", "post")
            .attr("action", fieldsForm.action);


        $("<input type='hidden'>")
            .attr("name", 'csrfmiddlewaretoken')
            .attr("value", $.cookie('csrftoken'))
            .appendTo(customDataFieldsForm);

        $('<input type="hidden">')
            .attr('name', 'data_fields')
            .attr('value', JSON.stringify(self.serialize()))
            .appendTo(customDataFieldsForm);
        customDataFieldsForm.appendTo("body");
        customDataFieldsForm.submit();
    };

}

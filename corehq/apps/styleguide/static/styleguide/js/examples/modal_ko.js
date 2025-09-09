import $ from 'jquery';
import ko from 'knockout';

let Item = function (id, name, description) {
    let self = {};
    self.id = ko.observable(id);
    self.name = ko.observable(name);
    self.description = ko.observable(description);
    return self;
};

$("#js-ko-demo-modal").koApplyBindings(function () {
    let self = {};
    self.items = ko.observableArray([
        Item(1, "First", "This is the first test item"),
        Item(2, "Second", "This is the second test item"),
    ]);
    self.itemBeingEdited = ko.observable(undefined);

    self.submitItemChanges = function () {
        for (let i = 0; i < self.items().length; i++) {
            if (self.items()[i].id() === self.itemBeingEdited().id()) {
                self.items()[i].name(self.itemBeingEdited().name());
                self.items()[i].description(self.itemBeingEdited().description());
            }
        }
        self.unsetItemBeingEdited();
    };
    self.unsetItemBeingEdited = function () {
        self.itemBeingEdited(undefined);
    };
    self.setItemBeingEdited = function (item) {
        let tempItem = Item(item.id(), item.name(), item.description());
        tempItem.modalTitle = "Editing Item '" + item.name() + "'";
        self.itemBeingEdited(tempItem);
    };
    return self;
});

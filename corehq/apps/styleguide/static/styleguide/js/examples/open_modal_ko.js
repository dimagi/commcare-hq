import ko from 'knockout';

$("#js-ko-demo-open-modal").koApplyBindings(function () {
    return {
        modalTitle: ko.observable("OpenModal Modal Example"),
        modalText: ko.observable("The modal obtains its knockout context from the context of the triggering element"),
    };
});

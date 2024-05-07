function TestApp() {
    return {
        myField: ko.observable('test'),
    };
}

$(function () {
    $("#ko-root").koApplyBindings(TestApp());
});
$(function () {
  $("#example-select2 .basic").select2();

  $("#example-select2 .ko-model-dynamic").koApplyBindings(function () {
    return {
      letters: ['eins', 'zwei', 'drei'],
      value: ko.observable('eins'),
    };
  });

  $("#example-select2 .ko-model-static").koApplyBindings();
});

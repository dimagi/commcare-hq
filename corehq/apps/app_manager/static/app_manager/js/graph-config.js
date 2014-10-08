var openGraphConfigurationModal = function(){
    var $modalDiv = $('<div data-bind="template: \'graph_configuration_modal\'"></div>');
    ko.applyBindings({}, $modalDiv.get(0));
    var $modal = $modalDiv.find('.modal');

    $modal.appendTo('body');
    $modal.modal('show');
    $modal.on('hidden', function () {
        $modal.remove();
    });
};
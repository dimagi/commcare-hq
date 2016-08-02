/* global ko */

ko.bindingHandlers.initWorkflow = {
    init: function(element, valueAccessor, allBindings, viewModel) {
        console.log('init workflow');
        var maxY = 0;
        var $W = $('#workspace');
        var workflows = $W.find('.workflow');
        workflows = _.first(workflows, workflows.length-1);
        if (workflows.length < 1) {
            maxY = -210;
        } else {
            _.each($W.find('.workflow'), function (elem) {
                var curY = $W.scrollTop() + $(elem).position().top;
                if (curY > maxY) {
                    maxY = curY;
                }
            });
        }

        $(element).draggable({
            containment: "#workspace",
            scroll: true,
            scrollSensitivity: 100,
            stack: '.workflow',
            cancel: '.ui-no-drag',
            drag: function (event, ui) {
                $(this).css('width', 'auto');
            },
            stop: valueAccessor()
        }).css('top', maxY + 210);
        
        viewModel.updateDistance();
    }
};

ko.bindingHandlers.initFormContainer = {
    init: function(element, valueAccessor) {
        $(element).droppable({
            accept: ".workflow-form",
            activeClass: 'ui-droppable-active',
            hoverClass: 'ui-droppable-hover',
            tolerance: 'touch',
            drop: valueAccessor(),
        });
    }
};

ko.bindingHandlers.initForm = {
    init: function(element, valueAccessor, allBindings, viewModel) {
        var $form = $(element);
        $form.detach();

        $(valueAccessor().selector())
            .find('.workflow-new-form')
            .before($form);

        $form.draggable({
            revert: 'invalid',
            cancel: '.ui-no-drag',
            helper: function (event) {
                return $(this).clone().appendTo('#workspace');
            },
            stop: function () {
                $(this).trigger('workflowBuilder.form.update');
            },
            opacity: 0.7
        });

        viewModel.updateOrder();
    }
};

ko.bindingHandlers.selectWorkflow = {
    init: function(element, valueAccessor) {
        $(element).on('workflowBuilder.workflow.deselect', function () {
            valueAccessor()(false);
        });
        $(element).click(function () {
            $('.workflow-name').trigger('workflowBuilder.workflow.deselect');
            valueAccessor()(true);
        });
    }
};

ko.bindingHandlers.selectForm = {
    init: function(element, valueAccessor) {
        $(element).on('workflowBuilder.form.deselect', function () {
            valueAccessor()(false);
        });
        $(element).click(function () {
            $('.workflow-form-title').trigger('workflowBuilder.form.deselect');
            valueAccessor()(true);
        });
    }
};

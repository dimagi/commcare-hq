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
        var $title = $(element).find('.workflow-category-title');
        var helpId = $title.attr('data-helptemp');
        $title.popover({
            content: function () {
                return $(helpId).text();
            },
            html: true,
            trigger: 'hover',
            placement: 'bottom',
            container: 'body'
        });
        var $recordList = $(element).find('.btn-workflow-records');
        if ($recordList) {
            $recordList.popover({
                title: "Record List",
                content: function () {
                    return $('#help-template-recordlist').text();
                },
                html: true,
                trigger: 'hover',
                placement: 'bottom',
                container: 'body'
            })
        }

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

ko.bindingHandlers.highlightRecordList = {
    init: function(element, valueAccessor) {
        $(element).mouseenter(function () {
            $('#' + valueAccessor()().draggableId()).find('.btn-workflow-records').addClass('glow');
        });

        $(element).mouseleave(function () {
            $('#' + valueAccessor()().draggableId()).find('.btn-workflow-records').removeClass('glow');
        });
    }
};


ko.bindingHandlers.animateScreen = {
    init: function(element, valueAccessor, allBindings, viewModel, bindingContext) {
        if (valueAccessor()()) {
            $(element).css('display', 'none');
        }
    },
    update: function(element, valueAccessor, allBindings, viewModel, bindingContext) {
        var $element = $(element),
            width = $element.width(),
            direction = viewModel.direction,
            duration = 300;
        if (valueAccessor()()) {
            var start = 0,
                end = direction === "forward" ? -width : width;
            $element.css("left", start)
                    .css("display", "block")
                    .animate({ left: end, }, duration);
        } else {
            var start = direction === "forward" ? width : -width,
                end = 0;
            $element.css("left", start)
                    .css("display", "block")
                    .animate({ left: end, }, duration);
        }
    }
};

/* globals hqDefine, hqImport */
hqDefine('commtrack/js/products_and_programs.async', function () {
    var CommtrackProductsProgramsViewModel = function (o) {
        var view_model = hqImport("hqwebapp/js/base_list_view_model").BaseListViewModel(o);

        view_model.currently_searching = ko.observable(false);

        view_model.colspan = ko.computed(function () {
            return 7;
        });

        view_model.init = function () {
            $(function () {
                view_model.change_page(view_model.current_page);
            });
        };

        view_model.change_page = function (page) {
            page = ko.utils.unwrapObservable(page);

            if (page) {
                view_model.currently_searching(true);
                $.ajax({
                    url: format_url(page),
                    dataType: 'json',
                    error: function () {
                        view_model.initial_load(true);
                        $('.hide-until-load').removeClass("hide");
                        $('#user-list-notification').text(gettext('Sorry, there was an problem contacting the server ' +
                            'to fetch the data. Please, try again in a little bit.'));
                        view_model.currently_searching(false);
                    },
                    success: reloadList,
                });
            }

            return false;
        };

        view_model.unsuccessful_archive_action = function (button) {
            return function (data) {
                if (data.message && data.product_id) {
                    var alert_container = $('#alert_' + data.product_id);
                    alert_container.text(data.message);
                    alert_container.show();
                }
                $(button).button('unsuccessful');
            };
        };

        var reloadList = function(data) {
            view_model.currently_searching(false);
            if (data.success) {
                if (!view_model.initial_load()) {
                    view_model.initial_load(true);
                    $('.hide-until-load').removeClass("hide");
                }
                view_model.current_page(data.current_page);
                view_model.data_list(data.data_list);
                view_model.archive_action_items([]);
            }
        };
        var format_url = function(page) {
            if (!page) {
                return "#";
            }
            return view_model.list_url +'?page=' + page +
                "&limit=" + view_model.page_limit() +
                "&show_inactive=" + view_model.show_inactive;
        };

        return view_model;
    };

    ko.bindingHandlers.isPrevNextDisabled = {
        update: function(element, valueAccessor) {
            var value = valueAccessor()();
            if (value === undefined) {
                $(element).parent().addClass('disabled');
            } else {
                $(element).parent().removeClass('disabled');
            }
        },
    };

    ko.bindingHandlers.isPaginationActive = {
        update: function(element, valueAccessor, allBindingsAccessor) {
            var current_page = parseInt(valueAccessor()());
            var current_item = parseInt(allBindingsAccessor()['text']);
            if (current_page === current_item) {
                $(element).parent().addClass('active');
            } else {
                $(element).parent().removeClass('active');
            }
        },
    };

    $(function(){
        var options = hqImport('hqwebapp/js/initial_page_data').get('program_product_options');
        _.each($('.ko-program-product-list'), function(list) {
            var viewModel = new CommtrackProductsProgramsViewModel(options);
            $(list).koApplyBindings(viewModel);
            viewModel.init();
        });
    });
});

hqDefine("campaign/js/async_configurable_report", [
    'jquery',
    'underscore',
    'bootstrap5',
    'hqwebapp/js/bootstrap5/alert_user',
    'reports/js/charts/main',
    'reports/js/filters/bootstrap5/main',
    'reports/js/util',
    'hqwebapp/js/bootstrap5/main',
    'hqwebapp/js/initial_page_data',
    'reports/js/bootstrap5/hq_report',
    'reports/js/bootstrap5/report_config_models',
    'reports/js/bootstrap5/standard_hq_report',
    // 'userreports/js/base',
    'commcarehq',
], function (
    $,
    _,
    bootstrap,
    alertUser,
    chartsMain,
    filtersMain,
    reportsUtil,
    hqMain,
    initialPageData,
    hqReport,
    reportConfigModels,
    standardHQReportModule,
) {
    return function (o) {
        var self = {};
        self.widgetFilters = o.widgetFilters;
        self.reportContent = o.reportContent;
        self.filterForm = o.filterForm;
        // self.loadingIssueModalElem = self.reportContent.find('#loadingReportIssueModal-' + o.reportId);
        // self.loadingIssueModal = new bootstrap.Modal(self.loadingIssueModalElem.get(0));
        self.issueAttempts = 0;
        self.urlRoot = o.urlRoot;
        
        // Make sure urlRoot ends with a slash
        if (self.urlRoot && !self.urlRoot.endsWith('/')) {
            self.urlRoot += '/';
        }
        
        self.hqLoading = null;
        self.standardReport = o.standardReport;
        self.filterRequest = null;
        self.reportRequest = null;
        self.queryIdRequest = null;
        self.loaderClass = '.report-loading';
        self.maxInputLimit = 4500;
        self.reportId = o.reportId;
        self.domain = o.domain || initialPageData.get('domain');

        self.humanReadableErrors = {
            400: gettext("Please check your Internet connection!"),
            404: gettext("Report Not Found."),
            408: gettext("Request timed out when rendering this report. This might be an issue with our servers" +
                " or with your Internet connection. We encourage you to report an issue to CommCare HQ Support so we" +
                " can look into any possible issues."),
            500: gettext("Problem Rendering Report. Our error monitoring tools have noticed this and we are working quickly to" +
                " resolve this issue as soon as possible. We encourage you to contact CommCare HQ Support" +
                " if this issue persists for more than a few minutes. We appreciate any additional information" +
                " you can give us about this problem so we can fix it immediately."),
            502: gettext("Bad Gateway. Please contact CommCare HQ Support."),
            503: gettext("CommCare HQ is experiencing server difficulties. We're working quickly to resolve it." +
                " Thank you for your patience. We are extremely sorry."),
            504: gettext("Gateway Timeout. Please contact CommCare HQ Support."),
            'maxInputError': gettext("Your search term was too long. Please provide a shorter search filter"),
        };

        var loadFilters = function (data) {
            self.filterRequest = null;
            try {
                // Hide loading indicator if it's still visible
                self.widgetFilters.find('#hq-report-filters-' + self.reportId + ' .loading-filters').hide();
                
                // Check if filters data exists
                if (data && data.filters) {
                    self.widgetFilters.find('#hq-report-filters-' + self.reportId).html(data.filters);
                    
                    // Initialize any JavaScript components in the filters
                    try {
                        if (typeof filtersMain !== 'undefined' && filtersMain.init) {
                            filtersMain.init();
                        }
                        
                        // Initialize any date pickers
                        self.widgetFilters.find('.date-picker').datepicker({
                            dateFormat: 'yy-mm-dd',
                            showButtonPanel: true,
                            changeMonth: true,
                            changeYear: true
                        });
                        
                        // Initialize any select2 dropdowns
                        self.widgetFilters.find('select.select2').each(function() {
                            $(this).select2();
                        });
                    } catch (e) {
                        // Error initializing filter components
                    }
                    
                    self.widgetFilters.find('#reportFiltersAccordion-' + self.reportId).removeClass('d-none');
                    if (self.standardReport && self.standardReport.resetFilterState) {
                        self.standardReport.resetFilterState();
                    }
                } else {
                    // If no filters data, show a message
                    self.widgetFilters.find('#hq-report-filters-' + self.reportId).html(
                        '<div class="alert alert-info">' + 
                        gettext('No filters available for this report.') + 
                        '</div>'
                    );
                }
            } catch (e) {
                // Show error message
                self.widgetFilters.find('#hq-report-filters-' + self.reportId).html(
                    '<div class="alert alert-danger">' + 
                    gettext('Error loading filters. Please try refreshing the page.') + 
                    '</div>'
                );
            }
        };

        self.init = function () {
            self.reportContent.attr('style', 'position: relative;');
            var initParams = window.location.search.substr(1);
            
            // First, load the filters - always load with empty params to get default filters
            self.updateFilters('');
            
            // Then, load the report if needed
            if (initParams && self.isCaseListRelated(self.urlRoot)) {
                self.getQueryId(initParams, true, self.standardReport.filterSet, self.urlRoot);
            } else {
                self.updateReport(true, '', self.standardReport.filterSet);
            }

            // only update the report if there are actually filters set
            if (!self.standardReport.needsFilters) {
                self.standardReport.filterSubmitButton.addClass('disabled');
            }
            self.filterForm.submit(function (e) {
                e.preventDefault();
                var params = reportsUtil.urlSerialize(this);
                
                if (self.isCaseListRelated(self.urlRoot)) {
                    var url = self.urlRoot + 'async/' + "?" + "&" + params;
                    if (url.length > self.maxInputLimit) {
                        alertUser.alert_user(self.humanReadableErrors['maxInputError'], "danger");
                    } else {
                        self.getQueryId(params, false, true, self.urlRoot);
                    }
                } else {
                    self.updateFilters(params);
                    self.updateReport(false, params, true);
                }
                return false;
            });
        };

        self.isCaseListRelated = function (pathName) {
            return pathName.includes('case_list');
        };

        self.getQueryId = function (params, initialLoad, setFilters, pathName) {
            // This only applies to Case List and Case List Explorer filter queries
            var queryId;
            if (params.includes('query_id=')) {
                queryId = params.replace('query_id=', '');
                params = '';
            } else {
                queryId = '';
            }
            
            var url = self.urlRoot + 'get_or_create_hash/';
            
            self.queryIdRequest = $.ajax({
                url: url,
                type: 'POST',
                dataType: 'json',
                data: {
                    'query_id': queryId,
                    'params': params,
                },
                success: function (data) {
                    self.queryIdRequest = null;
                    if (data.not_found) {
                        // no corresponding filter config found - redirect to the landing page
                        window.location.href = window.location.href.split('?')[0];
                    } else {
                        if (!initialLoad) { self.updateFilters(data.query_string); }
                        self.updateReport(initialLoad, data.query_string, setFilters);
                    }
                },
                error: function(xhr, status, error) {
                    // If there's an error, try to load the report anyway
                    if (!initialLoad) { self.updateFilters(params); }
                    self.updateReport(initialLoad, params, setFilters);
                }
            });
        };

        self.updateFilters = function (params) {
            self.standardReport.saveDatespanToCookie();
            
            // Show loading indicator
            self.widgetFilters.find('#hq-report-filters-' + self.reportId + ' .loading-filters').show();
            
            // For ConfigurableReportView, we need to use the correct URL format
            // The URL should be /a/{domain}/configurable/{report_id}/?format=json&hq_filters=true
            var url;

            // Check if urlRoot is already a complete URL
            if (self.urlRoot.includes('/configurable/')) {
                url = self.urlRoot;
                if (!url.endsWith('/')) {
                    url += '/';
                }
            } else {
                // Construct the URL for the ConfigurableReportView
                url = '/a/' + self.domain + '/configurable/' + self.reportId + '/';
            }
            
            // Add query parameters
            var queryParams = [];
            if (params) {
                queryParams.push(params);
            }
            queryParams.push('format=json');
            queryParams.push('hq_filters=true');
            
            url += '?' + queryParams.join('&');
            
            self.filterRequest = $.ajax({
                url: url,
                dataType: 'json',
                success: function(data) {
                    // Hide loading indicator
                    self.widgetFilters.find('#hq-report-filters-' + self.reportId + ' .loading-filters').hide();
                    
                    // Debug the response
                    if (data.filters) {
                        self.widgetFilters.find('#hq-report-filters-' + self.reportId).html(data.filters);
                    } else {
                        self.widgetFilters.find('#hq-report-filters-' + self.reportId).html(
                            '<div class="alert alert-info">' + 
                            gettext('No filters available for this report.') + 
                            '</div>'
                        );
                    }
                    
                    loadFilters(data);
                },
                error: function(xhr, status, error) {
                    // Hide loading indicator
                    self.widgetFilters.find('#hq-report-filters-' + self.reportId + ' .loading-filters').hide();
                    // Show error message
                    self.widgetFilters.find('#hq-report-filters-' + self.reportId).html(
                        '<div class="alert alert-danger">' + 
                        gettext('Error loading filters. Please try refreshing the page.') + 
                        '</div>'
                    );
                }
            });
        };

        self.updateReport = function (initialLoad, params, setFilters) {
            var processFilters = "";
            if (initialLoad) {
                processFilters = "hq_filters=true&";
                if (self.standardReport.loadDatespanFromCookie()) {
                    processFilters = processFilters +
                        "&startdate=" + self.standardReport.datespan.startdate +
                        "&enddate=" + self.standardReport.datespan.enddate;
                }
            }
            if (setFilters !== undefined) {
                processFilters = processFilters + "&filterSet=" + setFilters;
            }
            if (setFilters) {
                self.widgetFilters.find(self.standardReport.exportReportButton).removeClass('d-none');
                self.widgetFilters.find(self.standardReport.emailReportButton).removeClass('d-none');
                self.widgetFilters.find(self.standardReport.printReportButton).removeClass('d-none');
            }

            // For ConfigurableReportView, we need to use the correct URL format
            // The URL should be /a/{domain}/configurable/{report_id}/?format=json
            var url;
            
            // Check if urlRoot is already a complete URL
            if (self.urlRoot.includes('/configurable/')) {
                url = self.urlRoot;
                if (!url.endsWith('/')) {
                    url += '/';
                }
            } else {
                // Construct the URL for the ConfigurableReportView
                url = '/a/' + self.domain + '/configurable/' + self.reportId + '/';
            }
            
            // Add query parameters
            var queryParams = [];
            if (params) {
                queryParams.push(params);
            }
            if (processFilters) {
                queryParams.push(processFilters);
            }
            queryParams.push('format=json');
            
            url += '?' + queryParams.join('&');
            
            self.reportRequest = $.ajax({
                url: url,
                dataType: 'json',
                success: function (data) {
                    self.reportRequest = null;
                    
                    // Debug the response
                    if (data.report) {
                        self.reportContent.html(data.report);
                    } else {
                        self.reportContent.html(
                            '<div class="alert alert-info">' + 
                            gettext('No report content in response') + 
                            '</div>'
                        );
                    }
                    
                    if (data.filters) {
                        loadFilters(data);
                    }
                    self.issueAttempts = 0;
                    self.hqLoading = self.reportContent.find(self.loaderClass);
                    
                    // Initialize any JavaScript components in the report
                    try {
                        // Initialize charts if available
                        if (typeof chartsMain !== 'undefined' && chartsMain.init) {
                            chartsMain.init();
                        }
                        
                        // Initialize datatables if available
                        self.reportContent.find('table.datatable').each(function() {
                            $(this).DataTable({
                                responsive: true,
                                paging: true,
                                searching: true,
                                ordering: true,
                                info: true,
                                lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]]
                            });
                        });
                    } catch (e) {
                        // Error initializing report components
                    }
                    
                    // clear lingering popovers
                    _.each(self.reportContent.find('body > .popover'), function (popover) {
                        self.reportContent.find(popover).remove();
                    });
                    self.reportContent.append(self.hqLoading);
                    self.hqLoading.removeClass('d-none');

                    // Assorted UI cleanup/initialization
                    self.reportContent.find('.hq-report-time-notice').removeClass('d-none');

                    self.reportContent.find('.loading-backdrop').fadeOut();
                    self.hqLoading.fadeOut();

                    if (!initialLoad || !self.standardReport.needsFilters) {
                        self.standardReport.filterSubmitButton
                            .changeButtonState('reset');
                        setTimeout(function () {
                            // Bootstrap clears all btn styles except btn on reset
                            // This gets around it by waiting 10ms.
                            self.standardReport.filterSubmitButton
                                .removeClass('btn-primary')
                                .addClass('disabled')
                                .prop('disabled', true);

                        }, 10);
                    } else {
                        self.standardReport.filterSubmitButton
                            .changeButtonState('reset')
                            .addClass('btn-primary')
                            .removeClass('disabled')
                            .prop('disabled', false);
                    }
                },
                error: function (data) {
                    var humanReadable;
                    self.reportRequest = null;
                    if (data.status !== 0) {
                        // If it is a BadRequest allow for report to specify text
                        if (data.status === 400) {
                            humanReadable = data.responseText || self.humanReadableErrors[data.status];
                        } else {
                            humanReadable = self.humanReadableErrors[data.status];
                        }
                        self.issueAttempts += 1;
                    } else {
                        self.hqLoading = self.reportContent.find(self.loaderClass);
                        self.hqLoading.find('h4').text(gettext("Loading Stopped"));
                        self.hqLoading.find('.js-loading-spinner').attr('style', 'visibility: hidden;');
                    }
                },
                beforeSend: function () {
                    self.standardReport.filterSubmitButton.changeButtonState('loading');
                    self.reportContent.find('.loading-backdrop').fadeIn();
                    if (self.hqLoading) {
                        self.hqLoading.attr('style', 'position: absolute; top: 30px; left: 40%;');
                        self.hqLoading.fadeIn();
                    }
                },
            });
        };

        $(document).on('click', '.try-again', function () {
            // self.loadingIssueModalElem.find('.btn-primary').changeButtonState('loading');
            self.updateReport(self.initialLoad, '', self.standardReport.filterSet);
        });

        return self;
    };
}); 
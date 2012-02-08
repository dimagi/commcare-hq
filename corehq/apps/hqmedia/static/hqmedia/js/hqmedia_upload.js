/*
Requires jquery.form and jquery.progressbar
 */

function HQMediaUpload (args) {
    /* defaults...
        submit_url: '',
        progress_id_varname: 'X-Progress-ID',
        progress_checker_url: '',
        uploadbar: '#hqmedia_progressbar',
        processbar: null,
        progressbar_update_interval: 1000,
        upload_form_id: 'form#hqmedia_upload',
        upload_status_id: '#hqmedia_upload_status',
        static_url: '/static',
        form_error_class: '.error',
        process_complete_fn: function() {},
        max_retries: 4
     */

    var _submit_url = (args.submit_url) ? args.submit_url : '',
        _progress_checker_url = (args.progress_checker_url) ? args.progress_checker_url : '',
        _progress_id_var = (args.progress_id_varname) ? args.progress_id_varname : 'X-Progress-ID',
        _upload_progressbar = (args.uploadbar) ? $(args.uploadbar) : $('#hqmedia_progressbar'),
        _process_progressbar = (args.processbar) ? $(args.processbar): null,
        _process_checker_url = (args.process_checker_url) ? args.process_checker_url : '',
        _progress_bar_update_interval = (args.progressbar_update_interval) ? args.progressbar_update_interval : 4000,
        _upload_form_id = (args.upload_form_id) ? args.upload_form_id : 'form#hqmedia_upload',
        _submit_status_elem = (args.upload_status_id) ? $(args.upload_status_id) : $('#hqmedia_upload_status'),
        _static_url = (args.static_url) ? args.static_url : '/static',
        _error_class = (args.form_error_class) ? args.form_error_class : '.error',
        _max_retries = (args.max_retries) ? args.max_retries : 4;

    var _upload_form = $(_upload_form_id),
        _upload_form_errors = $(_upload_form_id+" "+_error_class),
        _upload_form_submit = $(_upload_form_id+" input[type='submit']");

    var $submitting_pinwheel = $("<img/>").attr("src", "/static/hqmedia/img/submitting.gif");

    var _process_complete_fn = (args.process_complete_fn) ? args.process_complete_fn : function (data) { };

    var submission_in_progress = false,
        poll_server_interval = 0,
        received_data = false,
        uploaded_file = null,
        last_known_upload_percentage = 0,
        last_known_processed_percentage = 0,
        upload_complete = false;

    var retrying = false,
        retry_attempts = 0;

    var progress_bar_options = {
            boxImage: _static_url+'hqmedia/img/progressbar.gif',
            barImage: {
                0:  _static_url+'hqmedia/img/progressbg_red.gif',
                30: _static_url+'hqmedia/img/progressbg_orange.gif',
                70: _static_url+'hqmedia/img/progressbg_green.gif'
            }
        };

    _upload_progressbar.progressBar(progress_bar_options);
    if(_process_progressbar)
        _process_progressbar.progressBar(progress_bar_options);

    function showProgressBars() {
        if (uploaded_file && !received_data && submission_in_progress && !upload_complete)
            _upload_progressbar.parent().fadeIn();
            if (_process_progressbar)
                _process_progressbar.parent().fadeIn();

            if (retrying && retry_attempts == _max_retries)
                _submit_status_elem.text('Retrying upload, please wait...').prepend($submitting_pinwheel);
            else
                _submit_status_elem.text('Uploading, please wait...').prepend($submitting_pinwheel);
    
            received_data = true;
    }

    function showRequest(formData, jqForm, options) {
        submission_in_progress = true;
        _upload_form_submit.fadeOut();
        //if (!received_data)
        //    _submit_status_elem.text('Verifying, please wait...').prepend($submitting_pinwheel);
        //uploaded_file = _upload_form.find("input[type='file']").val();
        // the next line is temporary
        _submit_status_elem.text('Uploading, please wait...').prepend($submitting_pinwheel);
        _submit_status_elem.fadeIn();
        return true;
    }

    function showResponse(response) {
        console.log(response);
        if(response) {
            var response_obj = $.parseJSON(response);
            if(response_obj.successful) {
                completeUpload();
                _process_complete_fn(response_obj);
            } else {
                cancelUpload();
                _submit_status_elem.fadeOut();
                processErrors(response_obj);
            }

        }
    }

    function stopPollingServer(progressStatus) {
        _upload_progressbar.progressBar(progressStatus);
        if(_process_progressbar)
            _process_progressbar.progressBar(progressStatus);
        clearInterval(poll_server_interval);
        poll_server_interval = 0;
        submission_in_progress = false;
    }

    function cancelUpload() {
        stopPollingServer(0);
        _upload_form_submit.fadeIn();
    }

    function completeUpload() {
        _upload_form_errors.text('');
        _submit_status_elem.text('Finished.');
        upload_complete = true;
        stopPollingServer(100);
    }

    function processErrors(error_list) {
        for(var error in error_list) {
            var error_div = "#errors_"+error;
            $(error_div).text('');
            var messages = error_list[error];
            for(var i=0; i < messages.length; i++) {
                $(error_div).append(messages[i]);
            }
        }
    }

    function generateHQMediaUrl(url, progress_id){
        return url+"?"+_progress_id_var+"="+progress_id;
    }

    function retrySubmitAttempt() {
        if(retry_attempts < _max_retries) {
            _upload_progressbar.progressBar(0);
            if(_process_progressbar)
                _process_progressbar.progressBar(0);
            retry_attempts += 1;
            retrying = true;
            _upload_form.submit();
        } else {
            retrying = false;
            cancelUpload();
            _submit_status_elem.text("Unfortunately there seems to be an error uploading the file. Please retry.");
        }
    }

    function startProgressBarUpdates(progress_id) {
        if(poll_server_interval != 0)
            clearInterval(poll_server_interval);
        if(submission_in_progress) {
            poll_server_interval = setInterval(function() {
                $.getJSON(generateHQMediaUrl(_progress_checker_url, progress_id), function (data) {
                    if (data == null) {
                        if(_process_checker_url && submission_in_progress)
                            $.getJSON(generateHQMediaUrl(_process_checker_url, progress_id), function(data) {
                                if(data === null) {
                                    stopPollingServer(0);
                                    retrySubmitAttempt();
                                    return;
                                }
                                showProgressBars();
                                completeUpload();
                                _process_complete_fn(data);
                            });
                        else
                            stopPollingServer(100);
                        return;
                    }
                    if(data.upload_aborted) {
                        cancelUpload();
                        _submit_status_elem.fadeOut();
                        if(data.error_list)
                            processErrors(data.error_list);
                        return;
                    }
                    showProgressBars();
                    _upload_form_errors.text('');

                    if(!data.upload_complete) {
                        var upload_percentage = Math.floor(100 * parseInt(data.uploaded) / parseInt(data.length));
                        if (upload_percentage >= last_known_upload_percentage && !(upload_percentage > 100)) {
                            last_known_upload_percentage = upload_percentage;
                            _upload_progressbar.progressBar(upload_percentage);
                        }
                    }

                    if(_process_progressbar){
                        var processed_percentage = Math.floor(100 * parseInt(data.processed) / parseInt(data.processed_length));
                        if (processed_percentage >= last_known_processed_percentage && !(processed_percentage > 100)) {
                            last_known_processed_percentage = processed_percentage;
                            _process_progressbar.progressBar(processed_percentage);
                            
                            // Such an hack, I'm so very sorry
                            if (last_known_upload_percentage < 75 && processed_percentage > 1) {
                                last_known_upload_percentage = 75;
                                _upload_progressbar.progressBar(last_known_upload_percentage);
                            }
                        }
                    }
                });
            }, _progress_bar_update_interval);
        }
    }

    this.listenForUploads = function () {
        _upload_progressbar.parent().hide();
        _upload_progressbar.parent().addClass("prog-bar");
        if(_process_progressbar) {
            _process_progressbar.parent().hide();
            _process_progressbar.parent().addClass("prog-bar");
        }
        _submit_status_elem.fadeOut();
        _upload_form.submit(function(e) {
            var progress_id = $(this).children('.hqmedia_upload_id').val();
            if(progress_id) {
                received_data = false;
                upload_complete = false;
                _submit_status_elem.text('');
                var ajax_submit_options = {
                    dataType: 'text',
                    url: generateHQMediaUrl(_submit_url, progress_id),
                    beforeSubmit: showRequest,
                    success: showResponse,
                    type: 'post'
                };
                $(this).ajaxSubmit(ajax_submit_options);
                // startProgressBarUpdates(progress_id);
            } else
                console.log("No upload id was provided!");
            

            return false;
        });
    }
    
}

function guidGenerator() {
    // from http://stackoverflow.com/questions/105034/how-to-create-a-guid-uuid-in-javascript
    var S4 = function() {
       return (((1+Math.random())*0x10000)|0).toString(16).substring(1);
    };
    return (S4()+S4()+"-"+S4()+"-"+S4()+"-"+S4()+"-"+S4()+S4()+S4());
}
describe('Form Workflow', function () {
    var workflow;
    var FormWorkflow = hqImport('app_manager/js/forms/form_workflow').FormWorkflow;

    describe('#workflowOptions', function () {
        const Toggles = hqImport('hqwebapp/js/toggles'),
            sandbox = sinon.sandbox.create();

        sandbox.stub(Toggles, 'toggleEnabled').withArgs('FORM_LINK_ADVANCED_MODE').returns(true);

        beforeEach(function () {
            var labels = {},
                options = {};

            labels[FormWorkflow.Values.DEFAULT] = 'Home Screen';
            labels[FormWorkflow.Values.ROOT] = 'First Menu';
            options = {
                labels: labels,
                workflow: FormWorkflow.Values.ROOT,
            };

            workflow = new FormWorkflow(options);
        });

        it('Should generate correct workflowOptions default', function () {
            var options = workflow.workflowOptions(),
                default_;

            assert.equal(options.length, 2);
            default_ = _.find(options, function (d) { return d.value === FormWorkflow.Values.DEFAULT; });

            assert.equal(default_.label, '* Home Screen');
            assert.equal(default_.value, FormWorkflow.Values.DEFAULT);

        });

        it('Should generate correct workflowOptions for non-defaults', function () {
            var options = workflow.workflowOptions(),
                root;

            assert.equal(options.length, 2);
            root = _.find(options, function (d) { return d.value === FormWorkflow.Values.ROOT; });
            assert.equal(root.label, 'First Menu');
            assert.equal(root.value, FormWorkflow.Values.ROOT);
        });
    });

    describe('FormLink workflow', function () {
        var labels = {},
            options = {};
        beforeEach(function () {

            labels[FormWorkflow.Values.FORM] = 'Form Link';
            options = {
                labels: labels,
                workflow: FormWorkflow.Values.FORM,
            };
        });

        it('Should generate correctly initializing config variables', function () {
            workflow = new FormWorkflow(options);

            assert.isTrue(workflow.showFormLinkUI());
            assert.lengthOf(workflow.forms, 0);
            assert.lengthOf(workflow.formLinks(), 0);
        });

        it('#onAddFormLink', function () {
            options.forms = [
                { name: 'My First Form', unique_id: 'abc123', auto_link: true },
                { name: 'My Second Form', unique_id: 'def456', auto_link: false },
            ];
            workflow = new FormWorkflow(options);
            assert.lengthOf(workflow.forms, 2);
            assert.lengthOf(workflow.formLinks(), 0);

            FormWorkflow.prototype.onAddFormLink.call(workflow, workflow, {});
            assert.lengthOf(workflow.formLinks(), 1);
        });

        it('Should ignore links to non-existent forms', function () {
            var realID = 'abc123',
                fakeID = 'nope123';
            options.forms = [
                { name: 'My First Form', unique_id: realID, auto_link: true },
            ];
            options.formLinks = [
                { xpath: "true()", doc_type: "FormLink", form_id: realID, datums: [], uniqueId: realID },
                { xpath: "false()", doc_type: "FormLink", form_id: fakeID, datums: [], uniqueId: fakeID },
            ];
            workflow = new FormWorkflow(options);
            assert.lengthOf(workflow.forms, 1);
            assert.lengthOf(workflow.formLinks(), 1);
        });
    });
});

import sinon from "sinon";
import serverLocationSelect from 'registration/js/server_location_select';

describe('serverLocationSelect', function () {

    it('should use initialValue when provided', function () {
        const url = 'https://test.commcarehq.org';
        const model = serverLocationSelect({
            initialValue: 'custom',
            url: url,
        });
        assert.equal(model.serverLocation(), 'custom');
    });

    it('should use current HQ subdomain if no initialValue', function () {
        const url = 'https://test.commcarehq.org';
        const model = serverLocationSelect({ url });
        assert.equal(model.serverLocation(), 'test');
    });

    it('should update url subdomain when serverLocation changes', function () {
        const url = 'https://test.commcarehq.org/some/path';
        const model = serverLocationSelect({ url });
        const navigateTo = sinon.stub(model, 'navigateTo');

        model.serverLocation('newsubdomain');
        sinon.assert.calledOnce(navigateTo);
        sinon.assert.calledWith(navigateTo, 'https://newsubdomain.commcarehq.org/some/path');
    });

    it('should not update url if same value is selected', function () {
        const url = 'https://test.commcarehq.org';
        const model = serverLocationSelect({ url });
        const navigateTo = sinon.stub(model, 'navigateTo');

        model.serverLocation('test');
        sinon.assert.notCalled(navigateTo);
    });

});

import sinon from "sinon";
import Middleware from "cloudcare/js/formplayer/middleware";

describe('SessionMiddle', function () {
    it('Should call middleware and apis with same arguments', function () {
        let middlewareSpy = sinon.spy(),
            result,
            API = {
                myRoute: sinon.spy(function (one, two, three) {
                    return one + two + three;
                }),
            };

        Middleware.middlewares = [middlewareSpy];

        let WrappedApi = Middleware.apply(API);

        result = WrappedApi.myRoute(1, 2, 3);

        // Ensure middleware is called and called with route name
        assert.isTrue(middlewareSpy.called);
        assert.deepEqual(middlewareSpy.getCall(0).args, ['myRoute']);

        // Ensure actual route is called with proper arguments and return value
        assert.deepEqual(API.myRoute.getCall(0).args, [1, 2, 3]);
        assert.equal(result, 6);
    });
});

from corehq.apps.api.resources.v0_4 import XFormInstanceResource


def convert_xform_to_json(xform):
    res = XFormInstanceResource()
    bundle = res.build_bundle(obj=xform)
    return res.serialize(None, res.full_dehydrate(bundle), 'application/json')

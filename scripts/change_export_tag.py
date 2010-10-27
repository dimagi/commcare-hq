from couchforms.models import XFormInstance

def run():
    instances = XFormInstance.view('couchforms/xform').all()
    for instance in instances:
        instance["#export_tag"] = ["domain", "xmlns"]
        instance.save()
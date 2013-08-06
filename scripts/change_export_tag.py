from couchforms.models import XFormInstance

def run():
    instances = XFormInstance.view('couchforms/by_xmlns', include_docs=True).all()
    for instance in instances:
        instance["#export_tag"] = ["domain", "xmlns"]
        instance.save()
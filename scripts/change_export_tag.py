from couchforms.models import XFormInstance

def run():
    instances = XFormInstance.view('hqadmin/forms_over_time', include_docs=True).all()
    for instance in instances:
        instance["#export_tag"] = ["domain", "xmlns"]
        instance.save()
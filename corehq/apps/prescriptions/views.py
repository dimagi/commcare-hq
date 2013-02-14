import json
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.http import require_POST

from corehq.apps.domain.decorators import require_superuser
from corehq.apps.prescriptions.forms import PrescriptionForm
from corehq.apps.prescriptions.models import Prescription

@require_superuser
def all_prescriptions(request, template='prescriptions/all.html'):
    prescriptions = Prescription.all()
    return render(request, template, {
        'prescriptions': prescriptions,
    })

@require_superuser
def add_prescription(request, prescription_id=None, template='prescriptions/add.html'):
    if prescription_id:
        prescription = Prescription.get(prescription_id)
    else:
        prescription = None
        
    if request.method == "POST":
        form = PrescriptionForm(request.POST)
        if form.is_valid():
            if prescription:
                for attr, value in form.cleaned_data.items():
                    setattr(prescription, attr, value)
                prescription.save()
            else:
                Prescription(**form.cleaned_data).save()
            return HttpResponseRedirect(reverse('all_prescriptions', args=[]))
    else:
        if prescription:
            form = PrescriptionForm(initial={
                'type': prescription.type,
                'domain': prescription.domain,
                'start': prescription.start,
                'end': prescription.end,
                'params': json.dumps(prescription.params)
            })
        else:
            form = PrescriptionForm()
    return render(request, template, {
        'form': form,
    })

@require_superuser
@require_POST
def delete_prescription(request, prescription_id):
    prescription = Prescription.get(prescription_id)
    assert(prescription.doc_type == 'Prescription')
    prescription.delete()
    return HttpResponseRedirect(reverse('all_prescriptions', args=[]))

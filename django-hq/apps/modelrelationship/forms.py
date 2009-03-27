from django import forms
from django.forms import widgets
from django.forms import ModelForm
from django.forms import widgets
from models import *
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType

class EdgeTypeForm(ModelForm):
        
    parent_type = forms.ModelChoiceField(label=_('Parent Object'),queryset=ContentType.objects.all())
    child_type = forms.ModelChoiceField(label=_('Child Object'),queryset=ContentType.objects.all())
    
    class Meta:
        model = EdgeType
        
    def __init__(self,parent_typeid=None,child_typeid=None,*args,**kwargs):
        super(EdgeTypeForm,self).__init__(*args,**kwargs)
        if parent_typeid is not None:
            self.fields['parent_type'].queryset = ContentType.objects.all().filter(id=parent_typeid)            
        if child_typeid is not None:
            self.fields['child_type'].queryset = ContentType.objects.all().filter(id=child_typeid)

class EdgeForm(ModelForm):    
    
    #parent_id = forms.Field(widget=widgets.Select() , label=u'Transformation zone seen')
    parent_object = forms.ModelChoiceField(label=_('Parent Object'),queryset=ContentType.objects.all())
    child_object = forms.ModelChoiceField(label=_('Child Object'),queryset=ContentType.objects.all())
    #child_id = forms.Field(widget=widgets.Select()(choices=YESNO) , label=u'Transformation zone seen')
    
    def __init__(self, edgetype_id=None,*args,**kwargs):
        super(EdgeForm,self).__init__(*args,**kwargs)
        self.relationship = EdgeType.objects.all().get(id=edgetype_id)
        self.fields['parent_object'].label = _('Parent Object (%s):' % (self.relationship.parent_type.name))
        self.fields['parent_object'].queryset = self.relationship.parent_type.model_class().objects.all()
        self.fields['child_object'].label = _('Child Object (%s):' % (self.relationship.child_type.name))
        self.fields['child_object'].queryset = self.relationship.child_type.model_class().objects.all()
                

    class Meta:
        model = Edge
        exclude = ('relationship','parent_type','child_type','parent_id','child_id')    
        
        
    def clean(self):     
        cleaned_data = self.cleaned_data 
        self.cleaned_data['relationship'] = self.relationship               
        return self.cleaned_data
    

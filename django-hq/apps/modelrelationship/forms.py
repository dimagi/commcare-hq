from django import forms
from django.forms import widgets
from django.forms import ModelForm
from django.forms import widgets
from models import *
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.forms.util import ErrorList, ValidationError

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
            
   # def clean(self):
#        occurs = EdgeType.objects.all().filter(relationship=self.relationship,parent_object=self.cleaned_data['parent_object'],child_object=self.cleaned_data['child_object'])
#        if len(occurs) != 0:
#            raise ValidationError("This edge relationship already exists")
       # pass

class EdgeForm(ModelForm):        
    #parent_id = forms.Field(widget=widgets.Select() , label=u'Transformation zone seen')    
    child_object = forms.ModelChoiceField(label=_('Child Object'),queryset=ContentType.objects.all())
    parent_object = forms.ModelChoiceField(label=_('Parent Object'),queryset=ContentType.objects.all())
    #child_id = forms.Field(widget=widgets.Select()(choices=YESNO) , label=u'Transformation zone seen')
    
    def __init__(self, edgetype_id=None, parent_item_id=None, child_item_id=None,*args,**kwargs):
        super(EdgeForm,self).__init__(*args,**kwargs)
        self.relationship = EdgeType.objects.all().get(id=edgetype_id)
        
        self.fields['parent_object'].label = _('Parent Object (%s):' % (self.relationship.parent_type.name))
        if parent_item_id is not None:
            print parent_item_id
            self.fields['parent_object'].queryset = self.relationship.parent_type.model_class().objects.filter(id=parent_item_id)
        else:
            self.fields['parent_object'].queryset = self.relationship.parent_type.model_class().objects.all()
        
        
        self.fields['child_object'].label = _('Child Object (%s):' % (self.relationship.child_type.name))
        if child_item_id is not None:
            #print len(self.relationship.child_type.model_class().objects.filter(id=child_item_id))
            #print len(self.relationship.child_type.model_class().objects.all())
            self.fields['child_object'].queryset = self.relationship.child_type.model_class().objects.filter(id=child_item_id)      
        else:
            self.fields['child_object'].queryset = self.relationship.child_type.model_class().objects.all()                   

    class Meta:
        model = Edge
        exclude = ('relationship','parent_type','child_type','parent_id','child_id')            
        
    def clean(self):     
        if self._errors:
            print self._errors
            return
        cleaned_data = self.cleaned_data 
        self.cleaned_data['relationship'] = self.relationship 
        self.cleaned_data['parent_type'] = self.relationship.parent_type
        self.cleaned_data['parent_id'] = self.cleaned_data['parent_object'].id
        
        self.cleaned_data['child_type'] = self.relationship.child_type
        
        self.cleaned_data['child_id'] = self.cleaned_data['child_object'].id
        
        #need to check if this edge exists already
        occurs = Edge.objects.all().filter(relationship=self.relationship,parent_id=self.cleaned_data['parent_object'].id,child_id=self.cleaned_data['child_id'])
        if len(occurs) == 1:            
            print 'validation error'
            print len(occurs)
            raise ValidationError("This edge relationship already exists")        
                              
        return self.cleaned_data
    

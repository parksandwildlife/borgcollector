import json
from itertools import ifilter

from django import forms
from django.core.exceptions import ObjectDoesNotExist,ValidationError
from django.forms.widgets import HiddenInput,TextInput
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper

from tablemanager.models import (Normalise,NormalTable,Normalise_NormalTable,Publish,
        Publish_NormalTable,ForeignTable,Input,NormalTable,Workspace,DataSource,
        PublishChannel,Style,DatasourceType)
from borg_utils.form_fields import GroupedModelChoiceField,CachedModelChoiceField
from borg_utils.widgets import MultiWidgetLayout
from borg_utils.form_fields import GeoserverSettingForm,MetaTilingFactorField,GridSetField,BorgSelect
from borg_utils.forms import BorgModelForm
from borg_utils.spatial_table import SpatialTable
from django.template import Context, Template

class ForeignTableForm(BorgModelForm):
    """
    A form for ForeignTable Model
    """
    def __init__(self, *args, **kwargs):
        super(ForeignTableForm, self).__init__(*args, **kwargs)
        #remove the empty label
        #self.fields['server'].empty_label=None

        if 'instance' in kwargs and  kwargs['instance'] and kwargs['instance'].pk:
            self.fields['name'].widget.attrs['readonly'] = True
            #remote the "+" icon from html page because this field is readonly
            self.fields['server'].widget = self.fields['server'].widget.widget
            self.fields['server'].widget.attrs['readonly'] = True

    def save(self, commit=True):
        self.instance.enable_save_signal()
        return super(ForeignTableForm, self).save(commit)

    class Meta:
        model = ForeignTable
        fields = "__all__"
        widgets = {
                'server': BorgSelect(),
        }

class DataSourceForm(BorgModelForm):
    """
    A form for DataSource Model
    """
    def __init__(self, *args, **kwargs):
        super(DataSourceForm, self).__init__(*args, **kwargs)

        if 'instance' in kwargs and  kwargs['instance'] and kwargs['instance'].pk:
            self.fields['name'].widget.attrs['readonly'] = True
            self.fields['type'].widget.attrs['readonly'] = True

    def save(self, commit=True):
        self.instance.enable_save_signal()
        return super(DataSourceForm, self).save(commit)

    @classmethod
    def get_fields(cls,obj=None):
        if obj and obj.type == DatasourceType.DATABASE:
            return ["name","type","description","user","password","sql","vrt"]
        else:
            return ["name","type","description","vrt"]


    class Meta:
        model = DataSource
        fields = "__all__"
        widgets = {
                'type': BorgSelect(attrs={"onChange":"$('#datasource_form').submit()"}),
                'description': forms.TextInput(attrs={"style":"width:95%"})
        }

class InputForm(BorgModelForm):
    """
    A form for Input Model
    """
    INSERT_FIELDS = 100
    CHANGE_DATA_SOURCE = 101
    CHANGE_FOREIGN_TABLE = 102

    foreign_table = CachedModelChoiceField(queryset=ForeignTable.objects.all(),label_func=lambda table:table.name,required=False,choice_family="foreigntable",choice_name="foreigntable_options", 
            widget=BorgSelect(attrs={"onChange":"$('#input_form').append(\"<input type='hidden' name='_change_foreign_table' value=''>\"); $('#input_form').submit()"}))
    def __init__(self, *args, **kwargs):
        super(InputForm, self).__init__(*args, **kwargs)
        if 'instance' in kwargs and  kwargs['instance'] and kwargs['instance'].pk:
            self.fields['name'].widget.attrs['readonly'] = True

            #remote the "+" icon from html page because this field is readonly
            self.fields['data_source'].widget = self.fields['data_source'].widget.widget
            self.fields['data_source'].widget.attrs['readonly'] = True
            #remote the "+" icon from html page because this field is readonly
            self.fields['foreign_table'].widget.attrs['readonly'] = True

    def get_mode(self,data):
        if data and "_insert_fields" in data:
            return (InputForm.INSERT_FIELDS,"insert_fields",True,False,None)
        elif data and "_change_data_source" in data:
            return (InputForm.CHANGE_DATA_SOURCE,"change_data_source",True,False,('name','data_source'))
        elif data and "_change_foreign_table" in data:
            return (InputForm.CHANGE_DATA_SOURCE,"change_foreign_table",True,False,('name','data_source','foreign_table'))

        return super(InputForm,self).get_mode(data)

    def get_fields(self,obj=None):
        if obj and hasattr(obj,"data_source"):
            if obj.data_source.type == DatasourceType.DATABASE:
                if hasattr(obj,"foreign_table"):
                    return ["name","data_source","foreign_table","generate_rowid","source"]
                else:
                    return ["name","data_source","foreign_table"]
            else:
                return ["name","data_source","generate_rowid","source"]
        else:
            return ["name","data_source"]

    def insert_fields(self):
        self.data['source'] = self.instance.source
        self.fields['foreign_table'].queryset = ForeignTable.objects.filter(server=self.instance.data_source)
        self.fields['foreign_table'].choice_name = "foreigntable_options_{}".format(self.instance.data_source.name)
        self.fields['foreign_table'].widget.choices = self.fields['foreign_table'].choices

    def change_data_source(self):
        if not hasattr(self.instance,"data_source"):
            self.data['source'] = ""
        elif self.instance.data_source.type == DatasourceType.FILE_SYSTEM:
            self.data['source'] = self.instance.data_source.vrt
        elif self.instance.data_source.type == DatasourceType.DATABASE:
            self.fields['foreign_table'].queryset = ForeignTable.objects.filter(server=self.instance.data_source)
            self.fields['foreign_table'].choice_name = "foreigntable_options_{}".format(self.instance.data_source.name)
            self.fields['foreign_table'].widget.choices = self.fields['foreign_table'].choices
            self.data['source'] = ""
        else:
            self.data['source'] = ""

    def change_foreign_table(self):
        self.data['source'] = str(Template(self.instance.data_source.vrt).render(Context({'self':self.instance,'db':Input.DB_TEMPLATE_CONTEXT})))
        self.fields['foreign_table'].queryset = ForeignTable.objects.filter(server=self.instance.data_source)
        self.fields['foreign_table'].choice_name = "foreigntable_options_{}".format(self.instance.data_source.name)
        self.fields['foreign_table'].widget.choices = self.fields['foreign_table'].choices

    def save(self, commit=True):
        self.instance.enable_save_signal()
        return super(InputForm, self).save(commit)

    class Meta:
        model = Input
        fields = "__all__"
        widgets = {
                'data_source': BorgSelect(attrs={"onChange":"$('#input_form').append(\"<input type='hidden' name='_change_data_source' value=''>\"); $('#input_form').submit()"}),
        }

class NormalTableForm(BorgModelForm):
    """
    A form for NormalTable Model
    """
    def __init__(self, *args, **kwargs):
        super(NormalTableForm, self).__init__(*args, **kwargs)
        if 'instance' in kwargs and  kwargs['instance'] and kwargs['instance'].pk:
            self.fields['name'].widget.attrs['readonly'] = True

    def save(self, commit=True):
        self.instance.enable_save_signal()
        return super(NormalTableForm, self).save(commit)

    class Meta:
        model = NormalTable
        fields = "__all__"

class PublishChannelForm(BorgModelForm):
    """
    A form for PublishChannel Model
    """
    def __init__(self, *args, **kwargs):
        super(PublishChannelForm, self).__init__(*args, **kwargs)
        if 'instance' in kwargs and  kwargs['instance'] and kwargs['instance'].pk:
            self.fields['name'].widget.attrs['readonly'] = True

    def save(self, commit=True):
        self.instance.enable_save_signal()
        return super(PublishChannelForm, self).save(commit)

    class Meta:
        model = PublishChannel
        fields = "__all__"

class WorkspaceForm(BorgModelForm):
    """
    A form for Workspace Model
    """
    def __init__(self, *args, **kwargs):
        super(WorkspaceForm, self).__init__(*args, **kwargs)
        if 'instance' in kwargs and  kwargs['instance'] and kwargs['instance'].pk:
            self.fields['name'].widget.attrs['readonly'] = True

            self.fields['publish_channel'].widget = self.fields['publish_channel'].widget.widget
            self.fields['publish_channel'].widget.attrs['readonly'] = True

    def save(self, commit=True):
        self.instance.enable_save_signal()
        return super(WorkspaceForm, self).save(commit)

    class Meta:
        model = Workspace
        fields = "__all__"
        widgets = {
                'publish_channel': BorgSelect(),
        }

class NormaliseForm(BorgModelForm):
    """
    A form for Normalise Model
    """
    input_table = GroupedModelChoiceField('data_source',queryset=Input.objects.all(),required=True,choice_family="input",choice_name="input_options")
    dependents = forms.ModelMultipleChoiceField(queryset=NormalTable.objects.all(),required=False)
    output_table = forms.ModelChoiceField(queryset=NormalTable.objects.all(),required=False,widget=BorgSelect())

    def __init__(self, *args, **kwargs):
        kwargs['initial']=kwargs.get('initial',{})
        if 'instance' in kwargs and  kwargs['instance']:
            try:
                kwargs['initial']['output_table']=kwargs['instance'].normaltable
            except ObjectDoesNotExist:
                pass
            dependents = []
            for relation in (kwargs['instance'].relations):
                if relation:
                    for normal_table in relation.normal_tables:
                        if normal_table: dependents.append(normal_table)

            kwargs['initial']['dependents'] = dependents

        super(NormaliseForm, self).__init__(*args, **kwargs)
        if 'instance' in kwargs and  kwargs['instance'] and kwargs['instance'].pk:
            self.fields['name'].widget.attrs['readonly'] = True
            self.fields['output_table'].widget.attrs['readonly'] = True

    def _post_clean(self):
        super(NormaliseForm,self)._post_clean()
        if self.errors:
            return

        if 'output_table' in self.cleaned_data:
            self.instance.normal_table = self.cleaned_data['output_table']
        else:
            self.instance.normal_table = None

        if 'dependents' in self.cleaned_data:
            sorted_dependents = self.cleaned_data['dependents'].order_by('pk')
        else:
            sorted_dependents = []

        self.instance.init_relations()

        pos = 0
        normal_table_pos = 0
        length = len(sorted_dependents)
        for relation in (self.instance.relations):
            normal_table_pos = 0
            for normal_table in relation.normal_tables:
                relation.set_normal_table(normal_table_pos, sorted_dependents[pos] if pos < length else None)
                pos += 1
                normal_table_pos += 1

    def save(self, commit=True):
        self.instance.enable_save_signal()
        return super(NormaliseForm, self).save(commit)

    class Meta:
        model = Normalise
        fields = ('name','input_table','dependents','output_table','sql')

class PublishForm(BorgModelForm,GeoserverSettingForm):
    """
    A form for normal table's Publish Model
    """
    create_cache_layer = forms.BooleanField(required=False,label="create_cache_layer",initial=True)
    create_cache_layer.setting_type = "geoserver_setting"

    server_cache_expire = forms.IntegerField(label="server_cache_expire",min_value=0,required=False,initial=0,help_text="Expire server cache after n seconds (set to 0 to use source setting)")
    server_cache_expire.setting_type = "geoserver_setting"

    client_cache_expire = forms.IntegerField(label="client_cache_expire",min_value=0,required=False,initial=0,help_text="Expire client cache after n seconds (set to 0 to use source setting)")
    client_cache_expire.setting_type = "geoserver_setting"

    workspace = GroupedModelChoiceField('publish_channel',queryset=Workspace.objects.all(),required=True,choice_family="workspace",choice_name="workspace_choices",widget=BorgSelect())
    input_table = GroupedModelChoiceField('data_source',queryset=Input.objects.all(),required=False,choice_family="input",choice_name="input_options")
    dependents = forms.ModelMultipleChoiceField(queryset=NormalTable.objects.all(),required=False)

    def __init__(self, *args, **kwargs):
        kwargs['initial']=kwargs.get('initial',{})
        self.get_setting_from_model(*args,**kwargs)

        if 'instance' in kwargs and  kwargs['instance']:
            #populate the dependents field value from table data
            dependents = []
            for relation in (kwargs['instance'].relations):
                if relation:
                    for normal_table in relation.normal_tables:
                        if normal_table: dependents.append(normal_table)

            kwargs['initial']['dependents'] = dependents

        super(PublishForm, self).__init__(*args, **kwargs)
        if 'instance' in kwargs and  kwargs['instance'] and kwargs['instance'].pk:
            self.fields['name'].widget.attrs['readonly'] = True
            self.fields['workspace'].widget.attrs['readonly'] = True

    @classmethod
    def get_fields(cls,obj=None):
        if obj and SpatialTable.check_normal(obj.spatial_type):
            return ('name','workspace','interval','status','input_table','dependents','priority','sql','create_extra_index_sql')
        else:
            return ('name','workspace','interval','status','input_table','dependents','priority','kmi_title','kmi_abstract','sql','create_extra_index_sql',"create_cache_layer","server_cache_expire","client_cache_expire")

    def _post_clean(self):
        super(PublishForm,self)._post_clean()
        if self.errors:
            return

        #populate the value of the relation columns
        if 'dependents' in self.cleaned_data:
            sorted_dependents = self.cleaned_data['dependents'].order_by('pk')
        else:
            sorted_dependents = []

        self.instance.init_relations()

        pos = 0
        normal_table_pos = 0
        length = len(sorted_dependents)
        for relation in (self.instance.relations):
            normal_table_pos = 0
            for normal_table in relation.normal_tables:
                relation.set_normal_table(normal_table_pos, sorted_dependents[pos] if pos < length else None)
                pos += 1
                normal_table_pos += 1
    
        if self.instance and SpatialTable.check_spatial(self.instance.spatial_type):
            self.set_setting_to_model()

    def save(self, commit=True):
        self.instance.enable_save_signal()
        return super(PublishForm, self).save(commit)

    class Meta:
        model = Publish
        fields = ('name','workspace','interval','status','input_table','dependents','priority','kmi_title','kmi_abstract','sql','create_extra_index_sql')

class StyleForm(BorgModelForm):
    """
    A form for spatial table's Style Model
    """
    default_style = forms.BooleanField(required=False,initial=False)

    def __init__(self, *args, **kwargs):
        kwargs['initial']=kwargs.get('initial',{})
        instance = None
        if 'instance' in kwargs and  kwargs['instance']:
            instance = kwargs['instance']

        if instance:
            kwargs['initial']['default_style'] = kwargs['instance'].default_style

        super(StyleForm, self).__init__(*args, **kwargs)

        builtin_style = False
        if instance and instance.pk:
            self.fields['name'].widget.attrs['readonly'] = True

            self.fields['publish'].widget = self.fields['publish'].widget.widget
            self.fields['publish'].widget.attrs['readonly'] = True

            builtin_style = instance.name == "builtin"
            if builtin_style:
                self.fields['description'].widget.attrs['readonly'] = True
        
        options = json.loads(self.fields['sld'].widget.option_json)
        options['readOnly'] = builtin_style
        #import ipdb;ipdb.set_trace()
        self.fields['sld'].widget.option_json = json.dumps(options)



    def _post_clean(self):
        self.instance.set_default_style = self.cleaned_data['default_style']
        super(StyleForm,self)._post_clean()
        if self.errors:
            return


    class Meta:
        model = Style
        fields = ('name','publish','description','status','default_style','sld')
        widgets = {
                "publish": BorgSelect(),
                "description": forms.TextInput(attrs={"style":"width:95%"})
        }


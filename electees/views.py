import json

from django.http import HttpResponse,Http404
from django.shortcuts import  get_object_or_404
from django.shortcuts import redirect
from django.template import RequestContext, loader
from django.core.exceptions import PermissionDenied
from django.views.decorators.csrf import ensure_csrf_cookie
from django.forms.models import modelformset_factory,modelform_factory
from django.forms import CheckboxSelectMultiple
from django.core.urlresolvers import reverse

from electees.models import ElecteeGroup, ElecteeGroupEvent,ElecteeResource,EducationalBackgroundForm,BackgroundInstitution,ElecteeInterviewSurvey,SurveyPart,SurveyQuestion,SurveyAnswer
from mig_main.models import MemberProfile, AcademicTerm
from mig_main.utility import Permissions, get_previous_page,  get_message_dict
from member_resources.views import get_permissions as get_member_permissions
from history.models import Officer
from electees.forms import get_unassigned_electees,InstituteFormset,BaseElecteeGroupForm,AddSurveyQuestionsForm,ElecteeSurveyForm

def user_is_member(user):
    if hasattr(user,'userprofile'):
        if user.userprofile.is_member():
            return True
    return False
def get_permissions(user):
    permission_dict = get_member_permissions(user)
    permission_dict.update({
        'can_create_groups':Permissions.can_manage_electee_progress(user),
        'can_edit_resources':Permissions.can_manage_electee_progress(user),
        'can_edit_surveys':Permissions.can_manage_electee_progress(user),
        'can_complete_surveys':Permissions.can_complete_electee_survey(user),
        })
    return permission_dict
def get_common_context(request):
    context_dict=get_message_dict(request)
    context_dict.update({
        'request':request,
        'subnav':'electees',
        'new_bootstrap':True,
    })
    return context_dict
def view_electee_groups(request):
    e_groups = ElecteeGroup.objects.filter(term=AcademicTerm.get_current_term()).order_by('points')
    packets = ElecteeResource.objects.filter(term=AcademicTerm.get_current_term(),resource_type__is_packet=True).order_by('resource_type')
    resources = ElecteeResource.objects.filter(term=AcademicTerm.get_current_term(),resource_type__is_packet=False).order_by('resource_type')
    template = loader.get_template('electees/view_electee_groups.html')
    context_dict = {
        'groups':e_groups,
        'resources':resources,
        'packets':packets,
        }
    context_dict.update(get_common_context(request))
    context_dict.update(get_permissions(request.user))
    context = RequestContext(request, context_dict)
    return HttpResponse(template.render(context))

def edit_electee_groups(request):
    if not Permissions.can_manage_electee_progress(request.user):
        request.session['error_message']='You are not authorized to edit electee groups'
        return redirect('electees:view_electee_groups')
    e_groups = ElecteeGroup.objects.filter(term=AcademicTerm.get_current_term())
    ElecteeGroupFormSet = modelformset_factory(ElecteeGroup,form =BaseElecteeGroupForm,can_delete=True)
    if request.method =='POST':
        formset = ElecteeGroupFormSet(request.POST,prefix='groups')
        if formset.is_valid():
            instances=formset.save(commit=False)
            for instance in instances:
                if not instance.id:
                    instance.term = AcademicTerm.get_current_term()
                    instance.points = 0
                instance.save()
            formset.save_m2m()
            request.session['success_message']='Electee teams successfully updated'
            return redirect('electees:view_electee_groups')
        else:
            request.session['error_message']='Form is invalid. Please correct the noted errors'
    else:
        formset = ElecteeGroupFormSet(queryset=e_groups,prefix='groups')
    template = loader.get_template('generic_formset.html')
    context_dict = {
        'formset':formset,
        'prefix':'groups',
        'subsubnav':'groups',
        'has_files':False,
        'submit_name':'Update Electee Teams',
        'form_title':'Update/Add/Remove Electee Teams',
        'help_text':'Create the electee teams for this semester, and specify the leaders and officers. You can also remove or edit here.',
        'can_add_row':True,
        'base':'electees/base_electees.html',
        }
    context_dict.update(get_common_context(request))
    context_dict.update(get_permissions(request.user))
    context = RequestContext(request, context_dict)
    return HttpResponse(template.render(context))

@ensure_csrf_cookie
def edit_electee_group_membership(request):
    if not Permissions.can_manage_electee_progress(request.user):
        request.session['error_message']='You are not authorized to edit electee teams'
        return redirect('electees:view_electee_groups')
    if request.method =='POST':
        electee_groups_json=request.POST['electee_groups']
        electee_groups = json.loads(electee_groups_json)
        for group_id in electee_groups:
            members = electee_groups[group_id]
            group = ElecteeGroup.objects.get(id=group_id)
            group.members.clear()
            for member in members:
                group.members.add(MemberProfile.objects.get(uniqname=member))
        request.session['success_message']='Your changes have been saved'

    e_groups = ElecteeGroup.objects.filter(term=AcademicTerm.get_current_term())
    template = loader.get_template('electees/edit_electee_group_membership.html')
    context_dict = {
        'electee_groups':e_groups,
        'unassigned_electees':get_unassigned_electees(),
        'subsubnav':'members',
        }
    context_dict.update(get_common_context(request))
    context_dict.update(get_permissions(request.user))
    context = RequestContext(request, context_dict)
    return HttpResponse(template.render(context))

def edit_electee_group_points(request):
    if not Permissions.can_manage_electee_progress(request.user):
        request.session['error_message']='You are not authorized to edit electee team points.'
        return redirect('electees:view_electee_groups')
    GroupPointsFormSet = modelformset_factory(ElecteeGroupEvent,exclude=('related_event_id',),can_delete=True)
    term =AcademicTerm.get_current_term()
    if request.method =='POST':
        formset = GroupPointsFormSet(request.POST,prefix='group_points',queryset=ElecteeGroupEvent.objects.filter(related_event_id=None,electee_group__term=term))
        if formset.is_valid():
            formset.save()
            request.session['success_message']='Electee team points updated successfully'
            return redirect('electees:view_electee_groups')
        else:
            request.session['error_message']='Form is invalid. Please correct the noted errors.'
    else:
        formset = GroupPointsFormSet(prefix='group_points',queryset=ElecteeGroupEvent.objects.filter(related_event_id=None,electee_group__term=term))
    template = loader.get_template('generic_formset.html')
    context_dict = {
        'formset':formset,
        'prefix':'group_points',
        'subsubnav':'points',
        'has_files':False,
        'submit_name':'Update Electee Team Points',
        'form_title':'Update/Add Remove Electee Team Points',
        'help_text':'Track the electee team points. You should not note any points from threshold participation at service or social events here. Those are tabulated automatically.',
        'can_add_row':True,
        'base':'electees/base_electees.html',
        }
    context_dict.update(get_common_context(request))
    context_dict.update(get_permissions(request.user))
    context = RequestContext(request, context_dict)
    return HttpResponse(template.render(context))

def submit_background_form(request):
    if not user_is_member(request.user) or not (request.user.userprofile.memberprofile.standing.name=='Graduate'):
        request.session['error_message']='You are not authorized to submit an educational background form.'
        return redirect('electees:view_electee_groups')
    BackgroundForm = modelform_factory(EducationalBackgroundForm,exclude=('member','term',))
    existing_form = EducationalBackgroundForm.objects.filter(member=request.user.userprofile.memberprofile,term=AcademicTerm.get_current_term())
    if existing_form.exists():
        form = BackgroundForm(request.POST or None, prefix='background',instance=existing_form[0])
        formset= InstituteFormset(request.POST or None, prefix='institute',instance=existing_form[0])
    else:
        blank_form = EducationalBackgroundForm(member=request.user.userprofile.memberprofile,term=AcademicTerm.get_current_term())
        form = BackgroundForm(request.POST or None,prefix='background',instance=blank_form)
        formset= InstituteFormset(request.POST or None,prefix='institute',instance=blank_form)
    if request.method == 'POST':
        if form.is_valid():
            background_form = form.save(commit=False)
            formset[0].empty_permitted=False
            if formset.is_valid():
                background_form.save()
                form.save_m2m()
                formset.save()
                request.session['success_message']='Background form successfully'
                return redirect('electees:view_electee_groups')
            else:
                request.session['error_message']='Either there were errors in your prior degrees or you forgot to include one.'
        else:
            request.session['error_message']='There were errors in the submitted form, please correct the errors noted below.'
        
        
    template = loader.get_template('electees/submit_education_form.html')
    dp_ids=[]
    for count in range(len(formset)):
        dp_ids.append('id_institute-%d-degree_start_date'%(count))
        dp_ids.append('id_institute-%d-degree_end_date'%(count))
    context_dict = {
        'form':form,
        'formset':formset,
        'prefix':'institute',
        'dp_ids':dp_ids,
        'dp_ids_dyn':['degree_start_date', 'degree_end_date'],
        }
    context_dict.update(get_common_context(request))
    context_dict.update(get_permissions(request.user))
    context = RequestContext(request, context_dict)
    return HttpResponse(template.render(context))
def edit_electee_resources(request):
    if not Permissions.can_manage_electee_progress(request.user):
        request.session['error_message']='You are not authorized to edit electee resources.'
        return redirect('electees:view_electee_groups')
    ResourceFormSet = modelformset_factory(ElecteeResource,exclude=('term',),can_delete=True)
    term =AcademicTerm.get_current_term()
    if request.method =='POST':
        formset = ResourceFormSet(request.POST,request.FILES,prefix='resources',queryset=ElecteeResource.objects.filter(term=term))
        if formset.is_valid():
            instances=formset.save(commit=False)
            for instance in instances:
                instance.term=term
                instance.save()
            request.session['success_message']='Electee resources updated successfully'
            return redirect('electees:view_electee_groups')
        else:
            request.session['error_message']='Form is invalid. Please correct the noted errors.'
    else:
        formset = ResourceFormSet(prefix='resources',queryset=ElecteeResource.objects.filter(term=term))
    template = loader.get_template('generic_formset.html')
    context_dict = {
        'formset':formset,
        'prefix':'resources',
        'has_files':True,
        'submit_name':'Update Electee Resources',
        'form_title':'Update/Add/Remove Electee Resources for %s'%(unicode(term)),
        'help_text':'These are the full packets and their constituent parts. If you need a part that isn\'t listed here, contact the web chair.',
        'can_add_row':True,
        'base':'electees/base_electees.html',
        }
    context_dict.update(get_common_context(request))
    context_dict.update(get_permissions(request.user))
    context = RequestContext(request, context_dict)
    return HttpResponse(template.render(context))
    
def manage_survey(request):
    if not Permissions.can_manage_electee_progress(request.user):
        request.session['error_message']='You are not authorized to edit the electee survey.'
        return redirect('electees:view_electee_groups')
        
    template = loader.get_template('electees/manage_survey.html')
    term = AcademicTerm.get_current_term()
    current_survey = ElecteeInterviewSurvey.objects.filter(term = term)
    survey_exists = current_survey.exists()
    if survey_exists:
        survey_has_q = current_survey[0].questions.all().exists()
    else:
        survey_has_q = False
    context_dict = {
        'survey_exists':survey_exists,
        'parts_exist':SurveyPart.objects.all().exists(),
        'questions_exist':SurveyQuestion.objects.all().exists(),
        'survey_has_questions':survey_has_q,
        }
    context_dict.update(get_common_context(request))
    context_dict.update(get_permissions(request.user))
    context = RequestContext(request, context_dict)
    return HttpResponse(template.render(context))
def edit_survey_for_term(request,term_id):
    if not Permissions.can_manage_electee_progress(request.user):
        request.session['error_message']='You are not authorized to edit the electee survey.'
        return redirect('electees:view_electee_groups')
    SurveyForm = modelform_factory(ElecteeInterviewSurvey,exclude=('term','questions'))
    term = get_object_or_404(AcademicTerm,id=term_id)
    current_surveys = ElecteeInterviewSurvey.objects.filter(term = term)
    prefix='survey'
    if current_surveys.exists():
        current_survey=current_surveys[0]
        existed=True
    else:
        current_survey = ElecteeInterviewSurvey(term=term)
        existed = False
    if request.method =='POST':
        form = SurveyForm(request.POST,prefix=prefix,instance=current_survey)
        if form.is_valid():
            form.save()
            request.session['success_message']='Electee interview survey updated successfully'
            return redirect('electees:manage_survey')
        else:
            request.session['error_message']='Form is invalid. Please correct the noted errors.'
    else:
        form = SurveyForm(prefix=prefix,instance=current_survey)
    template = loader.get_template('generic_form.html')
    verb = 'Update' if existed else 'Add'
    context_dict = {
        'form':form,
        'prefix':prefix,
        'has_files':False,
        'submit_name':'Update Electee Survey',
        'form_title':verb+' Electee Interview Survey for %s'%(unicode(term)),
        'help_text':'This is the meta survey object that will group the questions for a particular term.',
        'base':'electees/base_electees.html',
        'dp_ids':['id_survey-due_date'],
        'back_button':{'link':reverse('electees:manage_survey'),'text':'To Survey Manager'},
        }
    context_dict.update(get_common_context(request))
    context_dict.update(get_permissions(request.user))
    context = RequestContext(request, context_dict)
    return HttpResponse(template.render(context))

def edit_survey(request):
    return redirect('electees:edit_survey_for_term',AcademicTerm.get_current_term().id)
    
def edit_survey_parts(request):
    if not Permissions.can_manage_electee_progress(request.user):
        request.session['error_message']='You are not authorized to edit the electee survey.'
        return redirect('electees:view_electee_groups')
    SurveyPartFormSet = modelformset_factory(SurveyPart)
    prefix='surveyparts'
   
    if request.method =='POST':
        formset = SurveyPartFormSet(request.POST,prefix=prefix,queryset=SurveyPart.objects.all())
        if formset.is_valid():
            formset.save()
            request.session['success_message']='Electee interview survey parts updated successfully'
            return redirect('electees:manage_survey')
        else:
            request.session['error_message']='Form is invalid. Please correct the noted errors.'
    else:
        formset = SurveyPartFormSet(prefix=prefix,queryset=SurveyPart.objects.all())
    template = loader.get_template('generic_formset.html')
    context_dict = {
        'formset':formset,
        'prefix':prefix,
        'has_files':False,
        'can_add_row':True,
        'submit_name':'Update Electee Survey Parts',
        'form_title':'Update Electee Interview Survey Parts',
        'help_text':'Add or edit the different parts of the survey. Questions will be associated with a particular part. Only those parts that have questions which appear in a given survey will be included in that survey. There should be no need to remove survey parts. If all questions in a part are required, leave that field blank.',
        'base':'electees/base_electees.html',
        'back_button':{'link':reverse('electees:manage_survey'),'text':'To Survey Manager'},
        }
    context_dict.update(get_common_context(request))
    context_dict.update(get_permissions(request.user))
    context = RequestContext(request, context_dict)
    return HttpResponse(template.render(context))
    
def edit_survey_questions(request):
    if not Permissions.can_manage_electee_progress(request.user):
        request.session['error_message']='You are not authorized to edit the electee survey.'
        return redirect('electees:view_electee_groups')
    SurveyQuestionFormSet = modelformset_factory(SurveyQuestion)
    prefix='surveyquestions'
   
    if request.method =='POST':
        formset = SurveyQuestionFormSet(request.POST,prefix=prefix,queryset=SurveyQuestion.objects.all())
        if formset.is_valid():
            formset.save()
            request.session['success_message']='Electee interview survey questions updated successfully'
            return redirect('electees:manage_survey')
        else:
            request.session['error_message']='Form is invalid. Please correct the noted errors.'
    else:
        formset = SurveyQuestionFormSet(prefix=prefix,queryset=SurveyQuestion.objects.all())
    template = loader.get_template('generic_formset.html')
    context_dict = {
        'formset':formset,
        'prefix':prefix,
        'has_files':False,
        'can_add_row':True,
        'submit_name':'Update Electee Survey Questions',
        'form_title':'Update Electee Interview Survey Questions',
        'help_text':'Add or edit the different questions for the survey. Questions will only be displayed if they are added to the current survey. There should be no need to remove survey parts. If there is no word limit for a question, leave that field blank.',
        'base':'electees/base_electees.html',
        'back_button':{'link':reverse('electees:manage_survey'),'text':'To Survey Manager'},
        }
    context_dict.update(get_common_context(request))
    context_dict.update(get_permissions(request.user))
    context = RequestContext(request, context_dict)
    return HttpResponse(template.render(context))

def add_survey_questions_for_term(request,term_id):
    if not Permissions.can_manage_electee_progress(request.user):
        request.session['error_message']='You are not authorized to edit the electee survey.'
        return redirect('electees:view_electee_groups')
    term = get_object_or_404(AcademicTerm,id=term_id)
    current_surveys = ElecteeInterviewSurvey.objects.filter(term = term)
    prefix='survey'
    if current_surveys.exists():
        current_survey=current_surveys[0]
        existed=True
    else:
        raise Http404

    if request.method =='POST':
        form = AddSurveyQuestionsForm(request.POST,prefix=prefix,instance=current_survey)
        if form.is_valid():
            form.save()
            request.session['success_message']='Electee survey questions updated successfully'
            return redirect('electees:manage_survey')
        else:
            request.session['error_message']='Form is invalid. Please correct the noted errors.'
    else:
        form = AddSurveyQuestionsForm(prefix=prefix,instance=current_survey)
    template = loader.get_template('generic_form.html')
    verb = 'Update' if existed else 'Add'
    context_dict = {
        'form':form,
        'prefix':prefix,
        'has_files':False,
        'submit_name':'Update Electee Survey Questions',
        'form_title':verb+' Electee Survey Questions for %s'%(unicode(term)),
        'help_text':'Add questions for the particular term\'s survey.',
        'base':'electees/base_electees.html',
        'back_button':{'link':reverse('electees:manage_survey'),'text':'To Survey Manager'},
        }
    context_dict.update(get_common_context(request))
    context_dict.update(get_permissions(request.user))
    context = RequestContext(request, context_dict)
    return HttpResponse(template.render(context))    

def add_survey_questions(request):
    return redirect('electees:add_survey_questions_for_term',AcademicTerm.get_current_term().id)
    
    
def preview_survey_for_term(request,term_id):
    if not Permissions.can_manage_electee_progress(request.user):
        request.session['error_message']='You are not authorized to preview the electee survey.'
        return redirect('electees:view_electee_groups')
    term = get_object_or_404(AcademicTerm,id=term_id)
    current_surveys = ElecteeInterviewSurvey.objects.filter(term = term)
    if current_surveys.exists():
        current_survey=current_surveys[0]
        existed=True
    else:
        raise Http404
        
    template = loader.get_template('electees/preview_survey.html')
    context_dict = {
        'real_form':False,
        'questions':current_survey.questions.all(),
    }
    context_dict.update(get_common_context(request))
    context_dict.update(get_permissions(request.user))
    context = RequestContext(request, context_dict)
    return HttpResponse(template.render(context)) 
    
def preview_survey(request):
    return redirect('electees:preview_survey_for_term',AcademicTerm.get_current_term().id)
 
def complete_survey_for_term(request,term_id):
    if not Permissions.can_complete_electee_survey(request.user):
        request.session['error_message']='You are not authorized to preview the electee survey.'
        return redirect('electees:view_electee_groups')
        
    term = get_object_or_404(AcademicTerm,id=term_id)
    current_surveys = ElecteeInterviewSurvey.objects.filter(term = term)
    submitter=request.user.userprofile.memberprofile
    if current_surveys.exists():
        current_survey=current_surveys[0]
        existed=True
    else:
        raise Http404
    questions = current_survey.questions.all()
    if request.method =='POST':
        form = ElecteeSurveyForm(request.POST,questions=questions)
        if form.is_valid():
            print form.cleaned_data
            for (question, answer) in form.get_answers():

                existing_answer = SurveyAnswer.objects.filter(term=term,submitter=submitter,question=question)
                if existing_answer.exists():
                    old_answer = existing_answer[0]
                    if len(answer):
                        print existing_answer
                        print answer
                        old_answer.answer=answer
                        old_answer.save()
                    else:
                        existing_answer.delete()
                    
                else:
                    if len(answer):
                        new_answer = SurveyAnswer(term=term,submitter=submitter,answer=answer,question=question)
                        new_answer.save()
            request.session['success_message']='Electee survey updated successfully'
            return redirect('electees:view_electee_groups')
        else:
            request.session['error_message']='Form is invalid. Please correct the noted errors.'
    else:
        answers = SurveyAnswer.objects.filter(submitter=submitter,term=term,question__in=questions).distinct()
        form = ElecteeSurveyForm(questions=questions,answers=answers)
    template = loader.get_template('electees/complete_survey.html')
    
    context_dict = {
        'real_form':True,
        'form':form,
        'questions':questions,
    }
    context_dict.update(get_common_context(request))
    context_dict.update(get_permissions(request.user))
    context = RequestContext(request, context_dict)
    return HttpResponse(template.render(context)) 
    
def complete_survey(request):
    return redirect('electees:complete_survey_for_term',AcademicTerm.get_current_term().id)
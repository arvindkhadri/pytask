import os

from django.http import HttpResponse, Http404
from django.shortcuts import redirect, render_to_response
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

from pytask.taskapp.models import Task, Profile, Request
from pytask.taskapp.events.user import createUser, updateProfile
from pytask.taskapp.forms.user import UserProfileEditForm
from pytask.taskapp.events.request import reply_to_request
from pytask.taskapp.utilities.request import get_request

def show_msg(user, message, redirect_url=None, url_desc=None):
    """ simply redirect to homepage """
    
    return render_to_response('show_msg.html',{'user':user, 'message':message, 'redirect_url':redirect_url, 'url_desc':url_desc})

def homepage(request):
    """ check for authentication and display accordingly. """
    
    user = request.user
    is_guest = False
    is_mentor = False
    can_create_task = False
    task_list = []
    
    if not user.is_authenticated():
        is_guest = True
        disp_num = 10
        tasks_count = Task.objects.count()
        if tasks_count <= disp_num:
            task_list = Task.objects.order_by('id').reverse()
        else:
            task_list = Task.objects.order_by('id').reverse()[:10]
            
        return render_to_response('index.html', {'is_guest':is_guest, 'task_list':task_list})
        
    else:
        user_profile = user.get_profile()
        is_mentor = True if user.task_mentors.all() else False
        can_create_task = False if user_profile.rights == u"CT" else True
        notifications = user.notification_to.filter(deleted=False,is_read=False)
        requests = user.request_sent_to.filter(is_replied=False)
        
        context = {'user':user,
                   'is_guest':is_guest,
                   'is_mentor':is_mentor,
                   'task_list':task_list,
                   'can_create_task':can_create_task,
                   'notifications':notifications,
                   'requests':requests,
                   }
                   
        return render_to_response('index.html', context)

@login_required
def view_my_profile(request,uid=None):
    """ allows the user to view the profiles of users """
    if uid == None:
        edit_profile = True
        profile = Profile.objects.get(user = request.user)
        return render_to_response('user/my_profile.html', {'edit_profile':edit_profile,'profile':profile, 'user':request.user})
    edit_profile = True if request.user == User.objects.get(pk=uid) else False
    try:
        profile = Profile.objects.get(user = User.objects.get(pk=uid))
    except Profile.DoesNotExist:
        raise Http404
    return render_to_response('user/my_profile.html', {'edit_profile':edit_profile,'profile':profile, 'user':request.user})

@login_required
def edit_my_profile(request):
    """ enables the user to edit his/her user profile """
    if request.method == 'POST':
        form = UserProfileEditForm(request.POST)
#        if not form.is_valid():
#            edit_profile_form = UserProfileEditForm(instance = form)
#            return render_to_response('user/edit_profile.html',{'edit_profile_form' : edit_profile_form})
        if request.user.is_authenticated() == True:
            profile = Profile.objects.get(user = request.user)
            data = request.POST#form.cleaned_data
            properties = {'aboutme':data['aboutme'],
                          'foss_comm':data['foss_comm'],
                          'phonenum':data['phonenum'],
                          'homepage':data['homepage'],
                          'street':data['street'],
                          'city':data['city'],
                          'country':data['country'],
                          'nick':data['nick']}
            uploaded_photo = request.FILES.get('photo',None)
            prev_photo = profile.photo
            if uploaded_photo:
                if prev_photo:
                    os.remove(prev_photo.path)
                properties['photo'] = uploaded_photo
            #fields = ['dob','gender','credits','aboutme','foss_comm','phonenum','homepage','street','city','country','nick']
            updateProfile(profile,properties)
            return redirect('/user/view/uid='+str(profile.user_id))
    else:
        profile = Profile.objects.get(user = request.user)
        edit_profile_form = UserProfileEditForm(instance = profile)
        return render_to_response('user/edit_profile.html',{'edit_profile_form' : edit_profile_form, 'user':request.user})

@login_required
def browse_requests(request):
    
    user = request.user
    active_reqs = user.request_sent_to.filter(is_replied=False).exclude(is_valid=False)
    reqs = active_reqs.order_by('creation_date').reverse()

    context = {
        'user':user,
        'reqs':reqs,
    }

    return render_to_response('user/browse_requests.html', context)

@login_required
def view_request(request, rid):
    """ please note that request variable in this method is that of django.
    our app request is called user_request.
    """

    user = request.user
    user_request = get_request(rid, user)
    if not user_request:
        raise Http404

    user_request.is_read = True
    user_request.save()

    context = {
        'user':user,
        'req':user_request,
        'sent_users':user_request.sent_to.all()
    }

    return render_to_response('user/view_request.html', context)

@login_required
def process_request(request, rid, reply):
    """ check if the method is post and then update the request.
    if it is get, display a 404 error.
    """

    user = request.user
    browse_request_url= '/user/requests'
    req_obj = get_request(rid, user)

    if not req_obj:
        return show_msg(user, "Your reply has been processed", browse_request_url, "view other requests")

    if request.method=="POST":
        reply = True if reply == "yes" else False
        req_obj.remarks = request.POST.get('remarks', "")
        req_obj.save()

        reply_to_request(req_obj, reply, user)
        
        return show_msg(user, "Your reply has been processed", browse_request_url, "view other requests")
    else:
        return show_msg(user, "You are not authorised to do this", browse_request_url, "view other requests")

@login_required
def browse_notifications(request):
    """ get the list of notifications that are not deleted and display in datetime order.
    """

    user = request.user

    active_notifications = user.notification_to.filter(deleted=False).order_by('sent_date').reverse()
    for pos, notification in enumerate(reversed(active_notifications)):
        notification.pos = pos

    context = {
        'user':user,
        'notifications':active_notifications,
    }

    return render_to_response('user/browse_notifications.html', context)

@login_required
def view_notification(request, nid):
    """ get the notification depending on nid.
    Display it.
    """

    user = request.user
    notifications = user.notification_to.filter(deleted=False).order_by('sent_date')
    notification  = notifications[int(nid)]
    notification.is_read = True
    notification.save()

    context = {
        'user':user,
        'notification':notification,
    }

    return render_to_response('user/view_notification.html', context)

@login_required
def edit_notification(request, nid, action):
    """ if action is delete, set is_deleted.
    if it is unread, unset is_read.
    save the notification and redirect to browse_notifications.
    """

    user = request.user
    notifications = user.notification_to.filter(deleted=False).order_by('sent_date')
    notification = notifications[int(nid)]
    notifications_url = "/user/notifications/"

    if request.method == "POST":
        if action == "delete":
            notification.deleted = True
        elif action == "unread":
            notification.is_read = False
        
        notification.save()
        return redirect(notifications_url)
    else:
        return show_msg(user, 'This is wrong', notification_url, "view the notification")
   

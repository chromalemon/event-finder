from django.shortcuts import render
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth import login as auth_login, logout as auth_logout, get_user_model
from django.contrib.auth.decorators import login_required
from users.forms import CustomUserRegisterForm, CustomUserLoginForm, CustomUserProfileSearchForm

# Create your views here.

User = get_user_model()

def empty(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = CustomUserRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('dashboard')
    else:
        form = CustomUserRegisterForm()
    return render(request, 'users/register.html', {'form': form})
    
def login(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        
        form = CustomUserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, 'Login successful!')
            return redirect('dashboard')
    else:
        form = CustomUserLoginForm()
    return render(request, 'users/login.html', {'form': form})

@login_required
def logout(request):
    auth_logout(request)
    return redirect("home")

@login_required
def profile(request, user_id=None):
    user = request.user
    if user_id is None or user_id == user.id:
        return render(request, "users/view_profile.html", {"user": user, "own": True})
    user = get_object_or_404(User, id=user_id)
    return render(request, "users/view_profile.html", {"user": user, "own": False})
    
@login_required
def profile_search(request):
    if request.method == "POST":
        form = CustomUserProfileSearchForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data['query']
            try:
                user = User.objects.get(username=query)
            except User.DoesNotExist:
                user = None
            return render(request, "users/search_profile.html", {"form": form, "user": user})
    else:
        form = CustomUserProfileSearchForm()

    return render(request, "users/search_profile.html", {"form": form, "user": None})

@login_required
def profile_edit(request):
    if request.method == "POST":
        pass
    else:
        return HttpResponse("placeholder for profile edit page")
        #form = ProfileEditForm()


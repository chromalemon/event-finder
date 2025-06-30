from django.shortcuts import render
from django.contrib import messages
from django.shortcuts import redirect
from django.http import HttpResponse
from django.contrib.auth import login as auth_login, logout as auth_logout, get_user_model
from django.contrib.auth.decorators import login_required
from users.forms import CustomUserRegisterForm, CustomUserLoginForm

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
def profile(request):
    user = request.user
    if not user:
        return HttpResponse("User not found", status=404)
    
    return render(request, 'users/profile.html', {'user': user})

@login_required
def profile_detail(request, user_id):
    if user_id is None:
        return render(request, 'users/profile_detail.html', {'user': request.user})
    user = User.objects.get(id=user_id)
    if not user:
        return HttpResponse("User not found", status=404)
    return render(request, 'users/profile_detail.html', {'user': user})

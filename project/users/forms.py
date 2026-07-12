from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class CustomUserRegisterForm(UserCreationForm):

    email = forms.EmailField(
        required=True, 
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    username = forms.CharField(
        required=True,
        label='Username',
        widget=forms.TextInput(attrs={'autofocus': True, 'class': 'form-control'})
    )
    password1 = forms.CharField(
        required=True,
        label='Password',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password2 = forms.CharField(
        required=True,
        label='Confirm Password',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    dob = forms.DateField(
        required=False,
        initial=None,
        label='Date of Birth',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    profile_image = forms.ImageField(
        required=False,
        initial=None,
        label='Profile Image',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email', 'username', 'password1', 'password2', "dob", "profile_image")

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email is already registered.")
        return email

class CustomUserLoginForm(AuthenticationForm):
    """
    Custom login form that extends AuthenticationForm.
    """
    username = forms.CharField(
        required=True,
        label='Username',
        widget=forms.TextInput(attrs={'autofocus': True, 'class': 'form-control'})
    )
    password = forms.CharField(
        required=True,
        label='Password',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

class UserProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'profile_image']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get('email')
        if User.objects.filter(~Q(pk=self.instance.pk), email=email).exists():
            self.add_error("email", "Email is already registered.")
        return cleaned
        
    def save(self, commit=True):
        user = super().save(commit=False)

        pfp = self.cleaned_data.get("profile_image")

        if not pfp:
            user.profile_image = 'avatars/default.svg'

        if commit:
            user.save()

        return user

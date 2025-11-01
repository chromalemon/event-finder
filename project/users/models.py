from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, AbstractUser

# Create your models here.

class CustomUser(AbstractUser):
    """
    Custom user model that extends AbstractUser. 
    """
    
    email = models.EmailField(unique=True, max_length=255)
    dob = models.DateField(null=True, blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', default='default.jpg', null=True, blank=True)
    verified = models.BooleanField(default=False)

    

    def __str__(self):
        return self.email
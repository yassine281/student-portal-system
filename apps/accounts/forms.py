from django import forms
from .models import User


class UserProfileUpdateForm(forms.ModelForm):
    """Allows a user to update personal profile details and upload an avatar photo."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'avatar']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control bg-dark border-secondary text-white',
                'required': True,
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control bg-dark border-secondary text-white',
                'required': True,
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control bg-dark border-secondary text-white',
                'required': True,
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control bg-dark border-secondary text-white',
                'placeholder': '+7 (900) 555-0199',
            }),
            'avatar': forms.ClearableFileInput(attrs={
                'class': 'form-control bg-dark border-secondary text-white',
            }),
        }
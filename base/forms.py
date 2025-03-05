from django import forms

class PasswordForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput,
        label='Hasło',
        max_length=100
    )

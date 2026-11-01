from django import forms
from .models import Submission, Grade


class SubmissionForm(forms.ModelForm):
    """Form for students to upload assignment deliverables."""
    class Meta:
        model = Submission
        fields = ['submitted_file', 'notes']
        widgets = {
            'submitted_file': forms.ClearableFileInput(attrs={
                'class': 'form-control bg-dark border-secondary text-white'
            }),
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control bg-dark border-secondary text-white',
                'placeholder': 'Add optional notes or repository links for your instructor...',
            }),
        }


class GradeForm(forms.ModelForm):
    """Form for instructors to record weighted assessment scores."""
    class Meta:
        model = Grade
        fields = ['assignment_score', 'midterm_score', 'final_exam_score']
        widgets = {
            'assignment_score': forms.NumberInput(attrs={
                'class': 'form-control bg-dark border-secondary text-white',
                'step': '0.5', 'min': '0', 'max': '100'
            }),
            'midterm_score': forms.NumberInput(attrs={
                'class': 'form-control bg-dark border-secondary text-white',
                'step': '0.5', 'min': '0', 'max': '100'
            }),
            'final_exam_score': forms.NumberInput(attrs={
                'class': 'form-control bg-dark border-secondary text-white',
                'step': '0.5', 'min': '0', 'max': '100'
            }),
        }
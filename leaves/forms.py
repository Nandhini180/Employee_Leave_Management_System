from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import LeaveRequest, LeaveType
from .serializers import LeaveRequestCreateSerializer


class LeaveApplicationForm(forms.Form):
    leave_type = forms.ModelChoiceField(queryset=LeaveType.objects.all(), empty_label='Select leave type')
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Briefly explain the request'}))

    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.employee = employee
        self.validated_serializer = None

    def clean(self):
        cleaned_data = super().clean()
        if self.errors or not self.employee:
            return cleaned_data

        serializer = LeaveRequestCreateSerializer(
            data={
                'leave_type': cleaned_data['leave_type'].pk,
                'start_date': cleaned_data['start_date'],
                'end_date': cleaned_data['end_date'],
                'reason': cleaned_data['reason'],
            },
            context={'request': self._build_request_context()},
        )
        try:
            serializer.is_valid(raise_exception=True)
        except DjangoValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc
        except Exception as exc:
            detail = getattr(exc, 'detail', exc)
            raise forms.ValidationError(detail) from exc

        self.validated_serializer = serializer
        return cleaned_data

    def _build_request_context(self):
        class RequestLike:
            user = self.employee.user

        return RequestLike()

    def save(self):
        if not self.validated_serializer:
            raise ValueError('Form must be validated before saving.')
        return self.validated_serializer.save()


class ManagerDecisionForm(forms.Form):
    manager_note = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional note'}))
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Required only when rejecting'}),
    )

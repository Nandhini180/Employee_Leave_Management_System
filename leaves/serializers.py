from rest_framework import serializers

from .access import require_employee_profile
from .models import LeaveBalance, LeaveRequest, LeaveType
from .services import validate_leave_request


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ['id', 'name', 'max_days_per_year', 'is_paid', 'carry_forward']


class LeaveRequestSerializer(serializers.ModelSerializer):
    leave_type = LeaveTypeSerializer(read_only=True)
    employee_name = serializers.SerializerMethodField()
    reviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = [
            'id',
            'employee',
            'employee_name',
            'leave_type',
            'start_date',
            'end_date',
            'num_days',
            'reason',
            'status',
            'applied_at',
            'reviewed_by',
            'reviewer_name',
            'reviewed_at',
            'rejection_reason',
            'manager_note',
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        return obj.employee.user.get_full_name() or obj.employee.user.username

    def get_reviewer_name(self, obj):
        if not obj.reviewed_by:
            return ''
        return obj.reviewed_by.user.get_full_name() or obj.reviewed_by.user.username


class LeaveRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = ['id', 'leave_type', 'start_date', 'end_date', 'reason']

    def validate(self, attrs):
        employee = require_employee_profile(self.context['request'].user)
        validate_leave_request(employee, attrs['leave_type'], attrs['start_date'], attrs['end_date'])
        return attrs

    def create(self, validated_data):
        employee = require_employee_profile(self.context['request'].user)
        return LeaveRequest.objects.create(employee=employee, **validated_data)


class LeaveRequestActionSerializer(serializers.Serializer):
    manager_note = serializers.CharField(required=False, allow_blank=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=False)


class LeaveBalanceSerializer(serializers.ModelSerializer):
    leave_type = serializers.CharField(source='leave_type.name', read_only=True)
    remaining_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeaveBalance
        fields = ['id', 'leave_type', 'year', 'allocated_days', 'used_days', 'remaining_days']

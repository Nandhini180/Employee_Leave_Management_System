from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import NotFound


def get_employee_profile(user):
    try:
        return user.employee_profile
    except ObjectDoesNotExist:
        return None


def require_employee_profile(user):
    employee = get_employee_profile(user)
    if employee is None:
        raise NotFound('This user does not have an employee profile yet.')
    return employee

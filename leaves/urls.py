from django.urls import path

from . import views


urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('calendar/', views.team_calendar_view, name='team_calendar'),
    path('apply/', views.apply_leave, name='apply_leave'),
    path('leave/<int:pk>/cancel/', views.cancel_leave_web, name='cancel_leave_web'),
    path('manager/<int:pk>/approve/', views.approve_leave_web, name='approve_leave_web'),
    path('manager/<int:pk>/reject/', views.reject_leave_web, name='reject_leave_web'),
    path('api/leaves/', views.LeaveRequestListCreateAPIView.as_view(), name='api_leave_list_create'),
    path('api/leaves/<int:pk>/cancel/', views.LeaveCancelAPIView.as_view(), name='api_leave_cancel'),
    path('api/manager/pending/', views.ManagerPendingLeaveAPIView.as_view(), name='api_manager_pending'),
    path('api/manager/<int:pk>/approve/', views.ManagerApproveLeaveAPIView.as_view(), name='api_manager_approve'),
    path('api/manager/<int:pk>/reject/', views.ManagerRejectLeaveAPIView.as_view(), name='api_manager_reject'),
    path('api/balance/', views.LeaveBalanceAPIView.as_view(), name='api_leave_balance'),
]

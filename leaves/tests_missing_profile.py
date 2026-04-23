from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class MissingEmployeeProfileTests(TestCase):
    def test_dashboard_redirects_admin_without_profile_to_admin_site(self):
        user = User.objects.create_user(username='administrator', password='pass12345', is_staff=True, is_superuser=True)
        self.client.login(username='administrator', password='pass12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/admin/')

    def test_dashboard_renders_setup_page_for_non_admin_without_profile(self):
        user = User.objects.create_user(username='regularuser', password='pass12345')
        self.client.login(username='regularuser', password='pass12345')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Employee profile missing')

    def test_api_returns_not_found_when_profile_missing(self):
        user = User.objects.create_user(username='apiuser', password='pass12345')
        self.client.login(username='apiuser', password='pass12345')
        response = self.client.get(reverse('api_leave_balance'))
        self.assertEqual(response.status_code, 404)

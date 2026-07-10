from django.test import TestCase
from django.urls import reverse


class SmokeTests(TestCase):
	def test_home_page_returns_200(self):
		response = self.client.get(reverse("home"))

		self.assertEqual(response.status_code, 200)

	def test_dashboard_redirects_for_anonymous_users(self):
		response = self.client.get(reverse("dashboard"))

		self.assertEqual(response.status_code, 302)
		self.assertRedirects(
			response,
			f"{reverse('home')}?next={reverse('dashboard')}",
			fetch_redirect_response=False,
		)

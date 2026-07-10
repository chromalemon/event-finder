from django.test import TestCase
from django.urls import reverse

from django.contrib.auth import get_user_model


User = get_user_model()


class ProfileSearchTests(TestCase):
	def test_profile_search_finds_user_by_email(self):
		user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
		self.client.force_login(user)

		response = self.client.post(reverse("profile_search"), {"query": "alice@example.com"})

		self.assertContains(response, "alice")

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class UserViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="TestPass123!",
            first_name="Alice",
            last_name="Smith",
        )
        cls.other_user = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="TestPass123!",
        )

    # Registration

    def test_register_page_loads(self):
        response = self.client.get(reverse("register"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/register.html")

    def test_register_success(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "charlie",
                "email": "charlie@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(User.objects.filter(username="charlie").exists())
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_register_rejects_duplicate_email(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "charlie",
                "email": "alice@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="charlie").exists())
        self.assertFalse(response.context["form"].is_valid())

    def test_register_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "charlie",
                "email": "charlie@example.com",
                "password1": "StrongPass123!",
                "password2": "DifferentPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="charlie").exists())

    def test_authenticated_user_is_redirected_from_register(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("register"))

        self.assertRedirects(response, reverse("dashboard"))

    # Login

    def test_login_page_loads(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/login.html")

    def test_login_success(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "alice",
                "password": "TestPass123!",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_rejects_invalid_password(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "alice",
                "password": "WrongPassword123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_authenticated_user_is_redirected_from_login(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("login"))

        self.assertRedirects(response, reverse("dashboard"))

    # Logout

    def test_logout_requires_login(self):
        response = self.client.get(reverse("logout"))

        self.assertRedirects(
            response,
            f"/?next={reverse('logout')}",
        )

    def test_logout_success(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("logout"))

        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    # Profile viewing

    def test_profile_shows_own_profile(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/view_profile.html")
        self.assertEqual(response.context["user"], self.user)
        self.assertTrue(response.context["own"])

    def test_profile_shows_another_user(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("profile", args=[self.other_user.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"], self.other_user)
        self.assertFalse(response.context["own"])

    def test_profile_returns_404_for_unknown_user(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("profile", args=[999999]))

        self.assertEqual(response.status_code, 404)

    def test_profile_requires_login(self):
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 302)

    # Profile search

    def test_profile_search_finds_user_by_username(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("profile_search"),
            {"q": "bob"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"], self.other_user)

    def test_profile_search_finds_user_by_email(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("profile_search"),
            {"q": "bob@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"], self.other_user)

    def test_profile_search_is_case_insensitive(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("profile_search"),
            {"q": "BOB"},
        )

        self.assertEqual(response.context["user"], self.other_user)

    def test_profile_search_returns_no_user_for_unknown_query(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("profile_search"),
            {"q": "nobody@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["user"])

    def test_profile_search_with_empty_query(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("profile_search"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["user"])
        self.assertEqual(response.context["query"], "")

    # Profile editing

    def test_profile_edit_page_loads(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("profile_edit"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/edit_profile.html")

    def test_profile_edit_success(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Alicia",
                "last_name": "Jones",
                "email": "alicia@example.com",
            },
        )

        self.assertRedirects(response, reverse("profile"))

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Alicia")
        self.assertEqual(self.user.last_name, "Jones")
        self.assertEqual(self.user.email, "alicia@example.com")

    def test_profile_edit_rejects_duplicate_email(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "bob@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alice@example.com")

    def test_profile_edit_requires_login(self):
        response = self.client.get(reverse("profile_edit"))

        self.assertEqual(response.status_code, 302)


class ProfileSearchTests(TestCase):
    def test_profile_search_finds_user_by_email(self):
        user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass12345",
        )
        self.client.force_login(user)

        response = self.client.get(f"{reverse('profile_search')}?q=alice")

        self.assertContains(response, "alice@example.com")

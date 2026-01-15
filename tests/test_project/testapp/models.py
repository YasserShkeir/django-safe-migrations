"""Models for testapp."""

from django.db import models


class User(models.Model):
    """Test user model."""

    username = models.CharField(max_length=150, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Meta options."""

        app_label = "testapp"


class Profile(models.Model):
    """Test profile model - will be deleted in migration 0010."""

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)

    class Meta:
        """Meta options."""

        app_label = "testapp"

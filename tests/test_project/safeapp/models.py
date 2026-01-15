"""Models for safeapp."""

from django.db import models


class Article(models.Model):
    """Test article model with safe fields."""

    title = models.CharField(max_length=200)
    content = models.TextField(null=True, blank=True)
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Meta options."""

        app_label = "safeapp"

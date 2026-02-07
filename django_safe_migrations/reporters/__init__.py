"""Output reporters for migration issues."""

from django_safe_migrations.reporters.base import BaseReporter
from django_safe_migrations.reporters.console import ConsoleReporter
from django_safe_migrations.reporters.github import GitHubReporter
from django_safe_migrations.reporters.gitlab import GitLabReporter
from django_safe_migrations.reporters.json_reporter import JsonReporter
from django_safe_migrations.reporters.sarif import SarifReporter

__all__ = [
    "BaseReporter",
    "ConsoleReporter",
    "JsonReporter",
    "GitHubReporter",
    "GitLabReporter",
    "SarifReporter",
    "get_reporter",
]


def get_reporter(format_name: str, **kwargs: object) -> BaseReporter:
    """Get a reporter instance by format name.

    Args:
        format_name: One of 'console', 'json', 'github', 'gitlab', 'sarif'.
        **kwargs: Additional arguments to pass to the reporter.

    Returns:
        A reporter instance.

    Raises:
        ValueError: If the format name is not recognized.
    """
    reporters = {
        "console": ConsoleReporter,
        "json": JsonReporter,
        "github": GitHubReporter,
        "gitlab": GitLabReporter,
        "sarif": SarifReporter,
    }

    if format_name not in reporters:
        raise ValueError(
            f"Unknown format '{format_name}'. "
            f"Available formats: {', '.join(reporters.keys())}"
        )

    return reporters[format_name](**kwargs)  # type: ignore[no-any-return]

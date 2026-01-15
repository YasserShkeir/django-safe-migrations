# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security issues seriously. If you discover a security vulnerability in django-safe-migrations, please report it responsibly.

### How to Report

1. **Do NOT** create a public GitHub issue for security vulnerabilities
2. Email security concerns to: **shkeiryasser@gmail.com**
3. Include the following in your report:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: We will acknowledge receipt of your report within 48 hours
- **Assessment**: We will investigate and provide an initial assessment within 7 days
- **Resolution**: We aim to release a fix within 30 days for critical issues
- **Disclosure**: We will coordinate with you on public disclosure timing

### Scope

The following are in scope for security reports:

- Code execution vulnerabilities
- SQL injection (though this is unlikely given the library's nature)
- Path traversal issues
- Information disclosure
- Denial of service in the analyzer

The following are **out of scope**:

- Issues in dependencies (report these to the respective projects)
- Issues in Django itself (report to Django's security team)
- Social engineering attacks
- Physical security

## Security Best Practices

When using django-safe-migrations:

1. **Keep Updated**: Always use the latest version
2. **Review Suggestions**: The suggestions provided are examples; verify they're appropriate for your use case
3. **CI/CD Integration**: Run checks in CI to catch issues before production
4. **Don't Ignore Errors**: ERROR severity issues should be addressed before deploying

## Security Features

django-safe-migrations includes several security measures:

- **No Code Execution**: The library only analyzes migrations, it doesn't execute them
- **No Database Access**: By default, analysis is read-only and doesn't query the database
- **Static Analysis**: All checks are performed statically on migration files
- **Bandit Scanned**: All code is scanned with Bandit for security issues

## Credits

We appreciate responsible disclosure and will credit reporters in our release notes (unless you prefer to remain anonymous).

import secrets

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create (or reset) an admin: manage.py create_admin --email you@company.com --name 'Your Name'"

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", default="Administrator")

    def handle(self, *args, email, name, **opts):
        email = email.strip().lower()
        if "@" not in email:
            raise CommandError("Give a real email address.")
        password = secrets.token_urlsafe(12)
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User(email=email, name=name)
        user.role, user.hr_access, user.is_active, user.must_change_password = "admin", True, True, True
        user.failed_logins = user.mfa_failures = 0
        user.locked_until = None
        user.set_password(password)
        user.save()
        self.stdout.write(f"\nAdmin ready: {email}\nTemporary password (shown once): {password}\nYou'll choose a new password and set up two-factor at first sign-in.\n")

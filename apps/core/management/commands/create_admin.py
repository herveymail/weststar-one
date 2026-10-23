import secrets
import sys

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = ("Create (or reset) an admin: manage.py create_admin --email you@company.com --name 'Your Name' "
            "[--password-stdin]  (without it, a temporary password is printed and must be changed at first sign-in)")

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", default="Administrator")
        parser.add_argument("--password-stdin", action="store_true", help="Read the password from standard input (never from the command line).")

    def handle(self, *args, email, name, password_stdin, **opts):
        email = email.strip().lower()
        if "@" not in email:
            raise CommandError("Give a real email address.")
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User(email=email, name=name)
        if password_stdin:
            password = sys.stdin.readline().rstrip("\n")
            try:
                validate_password(password, user)
            except ValidationError as e:
                raise CommandError(" ".join(e.messages)) from e
        else:
            password = secrets.token_urlsafe(12)
        user.role, user.hr_access, user.is_active = "admin", True, True
        user.must_change_password = not password_stdin
        user.failed_logins = user.mfa_failures = 0
        user.locked_until = None
        user.set_password(password)
        user.save()
        if password_stdin:
            self.stdout.write(f"\nAdmin ready: {email}\nSign in with the password you chose; you'll set up two-factor at first sign-in.\n")
        else:
            self.stdout.write(f"\nAdmin ready: {email}\nTemporary password (shown once): {password}\nYou'll choose a new password and set up two-factor at first sign-in.\n")

"""
Management command to create a platform admin user
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import getpass
import secrets
import string

User = get_user_model()


class Command(BaseCommand):
    help = 'Create a platform admin user (custom admin dashboard access)'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Admin email address')
        parser.add_argument('--password', type=str, help='Admin password')
        parser.add_argument('--first-name', type=str, help='First name', default='Platform')
        parser.add_argument('--last-name', type=str, help='Last name', default='Admin')
        parser.add_argument('--superuser', action='store_true', help='Create as Django superuser (full admin access)')
        parser.add_argument('--generate-password', action='store_true', help='Auto-generate a strong password')

    def validate_password_strength(self, password):
        """Validate password strength"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"
        if not any(c in string.punctuation for c in password):
            return False, "Password must contain at least one special character"
        return True, "Password is strong"
    
    def generate_strong_password(self, length=16):
        """Generate a strong random password"""
        alphabet = string.ascii_letters + string.digits + string.punctuation
        while True:
            password = ''.join(secrets.choice(alphabet) for _ in range(length))
            is_valid, _ = self.validate_password_strength(password)
            if is_valid:
                return password

    def handle(self, *args, **options):
        email = options.get('email')
        password = options.get('password')
        first_name = options.get('first_name') or 'Platform'
        last_name = options.get('last_name') or 'Admin'
        is_superuser = options.get('superuser', False)
        generate_password = options.get('generate_password', False)

        # Interactive mode if email not provided
        if not email:
            while True:
                email = input('Email address: ').strip()
                try:
                    validate_email(email)
                    break
                except ValidationError:
                    self.stdout.write(self.style.ERROR('Invalid email address. Please try again.'))
        
        # Validate email
        try:
            validate_email(email)
        except ValidationError:
            self.stdout.write(self.style.ERROR(f'Invalid email address: {email}'))
            return
        
        # Handle password
        if generate_password:
            password = self.generate_strong_password()
            self.stdout.write(self.style.SUCCESS(f'\nGenerated strong password: {password}'))
            self.stdout.write(self.style.WARNING('Please save this password securely!'))
        elif not password:
            while True:
                password = getpass.getpass('Password: ')
                confirm_password = getpass.getpass('Confirm password: ')
                
                if password != confirm_password:
                    self.stdout.write(self.style.ERROR('Passwords do not match. Please try again.'))
                    continue
                
                is_valid, message = self.validate_password_strength(password)
                if not is_valid:
                    self.stdout.write(self.style.ERROR(f'{message}. Please try again.'))
                    continue
                
                break
        else:
            # Validate provided password
            is_valid, message = self.validate_password_strength(password)
            if not is_valid:
                self.stdout.write(self.style.ERROR(f'{message}'))
                return

        try:
            # Create platform admin or superuser
            if is_superuser:
                admin_user = User.objects.create_superuser(
                    email=email,
                    password=password
                )
                user_type = 'superuser'
            else:
                admin_user = User.objects.create_user(
                    email=email,
                    password=password,
                    role='admin',
                    is_staff=True,
                    is_active=True,
                    email_verified=True
                )
                user_type = 'platform admin'
            
            admin_user.first_name = first_name
            admin_user.last_name = last_name
            admin_user.save()

            self.stdout.write(self.style.SUCCESS(
                f'\n{user_type.capitalize()} user created successfully!'
            ))
            self.stdout.write(self.style.SUCCESS(
                f'Email: {email}'
            ))
            self.stdout.write(self.style.SUCCESS(
                f'Name: {admin_user.get_full_name()}'
            ))
            
            if is_superuser:
                self.stdout.write(self.style.SUCCESS(
                    f'\nAccess Django admin at: /admin/'
                ))
                self.stdout.write(self.style.SUCCESS(
                    f'Access platform admin at: /platformadmin/'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'\nAccess the platform admin at: /platformadmin/'
                ))
                self.stdout.write(self.style.WARNING(
                    f'\nNote: This is NOT a superuser. For Django admin access, use "python manage.py createplatformadmin --superuser"'
                ))

        except IntegrityError:
            self.stdout.write(self.style.ERROR(
                f'User with email {email} already exists!'
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'Error creating admin user: {str(e)}'
            ))

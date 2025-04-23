import csv
import os
from django.core.management.base import BaseCommand, CommandError
from evaluations.models import Student
from django.contrib.auth import get_user_model
from django.utils.text import slugify
import re

User = get_user_model()

class Command(BaseCommand):
    help = 'Import students from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing students instead of skipping them',
        )
        parser.add_argument(
            '--delimiter',
            type=str,
            default=',',
            help='CSV delimiter (default: ,)',
        )

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        update_existing = options['update']
        delimiter = options['delimiter']
        
        if not os.path.exists(csv_file_path):
            raise CommandError(f'File {csv_file_path} does not exist')
        
        count_created = 0
        count_skipped = 0
        count_updated = 0
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as csv_file:
                reader = csv.DictReader(csv_file, delimiter=delimiter)
                
                # Validate required fields
                required_fields = ['Nombre', 'Apellidos', 'Grupo', 'Dirección de correo']
                for field in required_fields:
                    if field not in reader.fieldnames:
                        raise CommandError(f'Required field "{field}" not found in CSV')
                
                for row in reader:
                    first_name = row['Nombre'].strip()
                    last_name = row['Apellidos'].strip()
                    group = row['Grupo'].strip()
                    email = row['Dirección de correo'].strip()
                    
                    # Skip empty rows
                    if not first_name or not last_name or not group or not email:
                        continue
                    
                    # Format full name
                    name = f"{first_name} {last_name}"
                    
                    # Check if user with this email already exists
                    user_exists = User.objects.filter(email=email).exists()
                    
                    if user_exists and not update_existing:
                        self.stdout.write(self.style.WARNING(f'Skipping existing user with email: {email}'))
                        count_skipped += 1
                        continue
                    
                    if user_exists:
                        # Update existing user
                        user = User.objects.get(email=email)
                        user.name = name
                        user.save()
                        
                        # Update or create student profile
                        student, created = Student.objects.update_or_create(
                            user=user,
                            defaults={'group': group}
                        )
                        
                        if not created:
                            count_updated += 1
                            self.stdout.write(self.style.SUCCESS(f'Updated student: {name} ({email}) - Group: {group}'))
                        else:
                            count_created += 1
                            self.stdout.write(self.style.SUCCESS(f'Created student profile for existing user: {name} ({email}) - Group: {group}'))
                    else:
                        # Create new user
                        user = User.objects.create(
                            name=name,
                            email=email,
                            is_active=True
                        )
                        
                        # Generate a secure password using email before the @ symbol
                        email_prefix = email.split('@')[0]
                        # Clean and sanitize the password
                        password = re.sub(r'[^a-zA-Z0-9]', '', email_prefix) + '123'
                        user.set_password(password)
                        user.save()
                        
                        # Create student profile
                        Student.objects.create(
                            user=user,
                            group=group
                        )
                        
                        count_created += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Created new student: {name} ({email}) - Group: {group} - Password: {password}'
                            )
                        )
                
                self.stdout.write(self.style.SUCCESS(
                    f'Import complete! Created: {count_created}, Updated: {count_updated}, Skipped: {count_skipped}'
                ))
                
        except Exception as e:
            raise CommandError(f'Error importing students: {str(e)}')

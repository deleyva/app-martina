import random
from django.core.management.base import BaseCommand
from evaluations.models import Student
from django.contrib.auth import get_user_model
from faker import Faker

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates fake users with student profiles for specific groups'

    def handle(self, *args, **options):
        fake = Faker(['es_ES'])  # Spanish locale for realistic Spanish names
        groups = ["AB", "CF", "D", "H"]
        
        # Delete existing students and users if they exist
        existing_students = Student.objects.filter(group__in=groups)
        existing_count = existing_students.count()
        
        if existing_count > 0:
            self.stdout.write(self.style.WARNING(f'Deleting {existing_count} existing students in groups {", ".join(groups)}'))
            
            # Get user IDs before deleting students
            user_ids = [student.user_id for student in existing_students if student.user_id]
            
            # Delete students
            existing_students.delete()
            
            # Delete associated users
            if user_ids:
                User.objects.filter(id__in=user_ids).delete()
                self.stdout.write(self.style.WARNING(f'Deleted {len(user_ids)} associated user accounts'))
        
        students_created = 0
        
        for group in groups:
            self.stdout.write(self.style.SUCCESS(f'Creating 20 students for group {group}'))
            
            for i in range(20):
                # Generate Spanish names
                name = f"{fake.first_name()} {fake.last_name()} {fake.last_name()}"  # Spanish style with two last names
                
                # Generate a unique email
                email = f"{name.lower().replace(' ', '.')}{i}@example.com"
                
                # Create the user
                user = User.objects.create(
                    name=name,
                    email=email,
                    is_active=True
                )
                
                # Set a simple password
                user.set_password("password123")
                user.save()
                
                # Create the student profile
                Student.objects.create(
                    user=user,
                    group=group
                )
                
                students_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {students_created} fake students with user accounts'))

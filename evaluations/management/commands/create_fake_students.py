import random
from django.core.management.base import BaseCommand
from evaluations.models import Student, Group
from django.contrib.auth import get_user_model
from faker import Faker

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates fake users with student profiles for specific groups'

    def handle(self, *args, **options):
        fake = Faker(['es_ES'])  # Spanish locale for realistic Spanish names
        group_names = ["1º ESO A", "1º ESO B", "2º ESO A", "2º ESO B"]
        
        # Crear grupos si no existen
        groups = []
        for group_name in group_names:
            group, created = Group.objects.get_or_create(name=group_name)
            groups.append(group)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group: {group_name}'))
        
        # Delete existing students and users if they exist
        existing_students = Student.objects.filter(group__in=groups)
        existing_count = existing_students.count()
        
        if existing_count > 0:
            self.stdout.write(self.style.WARNING(f'Deleting {existing_count} existing students in groups {", ".join(group_names)}'))
            
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
            self.stdout.write(self.style.SUCCESS(f'Creating 20 students for group {group.name}'))
            
            for i in range(20):
                # Generate Spanish names
                name = f"{fake.first_name()} {fake.last_name()} {fake.last_name()}"  # Spanish style with two last names
                
                # Generate a unique email (include group to make it unique across groups)
                email = f"{name.lower().replace(' ', '.')}.{group.name.lower().replace(' ', '')}.{i}@example.com"
                
                # Create the user
                user = User.objects.create(
                    name=name,
                    email=email,
                    is_active=True
                )
                
                # Set a simple password
                user.set_password("password123")
                user.save()
                
                # Create the student profile with FK to Group
                Student.objects.create(
                    user=user,
                    group=group  # Ahora es FK al objeto Group
                )
                
                students_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {students_created} fake students with user accounts'))

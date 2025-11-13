import random
from django.core.management.base import BaseCommand
from evaluations.models import Group
from django.contrib.auth import get_user_model
from faker import Faker

User = get_user_model()


class Command(BaseCommand):
    help = 'Creates fake teacher users and assigns them to groups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--teachers',
            type=int,
            default=5,
            help='Number of teachers to create (default: 5)'
        )

    def handle(self, *args, **options):
        fake = Faker(['es_ES'])  # Spanish locale for realistic Spanish names
        num_teachers = options['teachers']
        
        # Obtener o crear grupos
        group_names = ["1º ESO A", "1º ESO B", "2º ESO A", "2º ESO B"]
        groups = []
        for group_name in group_names:
            group, created = Group.objects.get_or_create(name=group_name)
            groups.append(group)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group: {group_name}'))
        
        # Eliminar profesores existentes si tienen email de ejemplo
        existing_teachers = User.objects.filter(
            is_staff=True,
            email__endswith='@profesor.example.com'
        )
        existing_count = existing_teachers.count()
        
        if existing_count > 0:
            self.stdout.write(self.style.WARNING(
                f'Deleting {existing_count} existing fake teacher accounts'
            ))
            existing_teachers.delete()
        
        teachers_created = 0
        
        self.stdout.write(self.style.SUCCESS(f'Creating {num_teachers} fake teachers'))
        
        for i in range(num_teachers):
            # Generate Spanish names
            name = f"{fake.first_name()} {fake.last_name()} {fake.last_name()}"
            
            # Generate unique email for teacher
            email = f"{name.lower().replace(' ', '.')}.profesor{i}@profesor.example.com"
            
            # Create the teacher user
            teacher = User.objects.create(
                name=name,
                email=email,
                is_active=True,
                is_staff=True  # Los profesores son staff
            )
            
            # Set a simple password
            teacher.set_password("password123")
            teacher.save()
            
            # Asignar a grupos aleatoriamente (cada profesor a 1-3 grupos)
            num_groups_to_assign = random.randint(1, 3)
            groups_to_assign = random.sample(groups, num_groups_to_assign)
            
            for group in groups_to_assign:
                group.teachers.add(teacher)
                self.stdout.write(
                    f'  → {teacher.name} asignado a {group.name}'
                )
            
            teachers_created += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully created {teachers_created} fake teachers with staff privileges'
        ))
        self.stdout.write(self.style.SUCCESS(
            'Password for all teachers: password123'
        ))

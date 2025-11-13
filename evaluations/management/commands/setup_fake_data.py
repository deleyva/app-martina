from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Setup complete fake data: creates groups, teachers, and students'

    def add_arguments(self, parser):
        parser.add_argument(
            '--teachers',
            type=int,
            default=5,
            help='Number of teachers to create (default: 5)'
        )
        parser.add_argument(
            '--skip-students',
            action='store_true',
            help='Skip creating students (only create groups and teachers)'
        )
        parser.add_argument(
            '--skip-teachers',
            action='store_true',
            help='Skip creating teachers (only create groups and students)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('SETUP FAKE DATA - COMPLETE SYSTEM'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        # 1. Crear profesores (esto también crea grupos)
        if not options['skip_teachers']:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('STEP 1: Creating fake teachers...'))
            self.stdout.write('-' * 60)
            call_command('create_fake_teachers', teachers=options['teachers'])
        
        # 2. Crear estudiantes (esto también crea grupos si no existen)
        if not options['skip_students']:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('STEP 2: Creating fake students...'))
            self.stdout.write('-' * 60)
            call_command('create_fake_students')
        
        # Resumen final
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('SETUP COMPLETE!'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        self.stdout.write('📚 Groups created: 1º ESO A, 1º ESO B, 2º ESO A, 2º ESO B')
        
        if not options['skip_teachers']:
            self.stdout.write(f'👨‍🏫 Teachers created: {options["teachers"]} (randomly assigned to 1-3 groups each)')
        
        if not options['skip_students']:
            self.stdout.write('👨‍🎓 Students created: 80 (20 per group)')
        
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Default password for all users: password123'))
        self.stdout.write('')
        self.stdout.write('Next steps:')
        self.stdout.write('  1. Login as a teacher to access: /evaluations/class-sessions/')
        self.stdout.write('  2. Login as a student to access: /evaluations/dashboard/')
        self.stdout.write('  3. Add content to group libraries: /evaluations/group-library/<id>/')
        self.stdout.write('')

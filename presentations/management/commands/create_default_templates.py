"""
Comando para crear plantillas de presentación por defecto
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from presentations.models import PresentationTemplate

User = get_user_model()


class Command(BaseCommand):
    help = 'Crea plantillas de presentación por defecto'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username del usuario que creará las plantillas (por defecto: primer superuser)',
        )

    def handle(self, *args, **options):
        # Obtener usuario
        username = options.get('user')
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Usuario "{username}" no encontrado')
                )
                return
        else:
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                self.stdout.write(
                    self.style.ERROR('No se encontró ningún superusuario. Crea uno primero.')
                )
                return

        # Plantillas por defecto
        templates_data = [
            {
                'name': 'Sesión de Clase Estándar',
                'description': 'Plantilla para presentaciones de sesiones de clase musicales',
                'template_type': 'class_session',
                'theme': 'default',
                'page_format': 'A4',
                'orientation': 'landscape',
                'is_public': True,
                'custom_css': '''
                .slide {
                    font-family: 'Arial', sans-serif;
                }
                .music-item {
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }
                '''
            },
            {
                'name': 'Colección Musical Colorida',
                'description': 'Plantilla vibrante para mostrar colecciones de elementos musicales',
                'template_type': 'music_collection',
                'theme': 'music',
                'page_format': 'A4',
                'orientation': 'portrait',
                'is_public': True,
                'custom_css': '''
                .slide {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .music-item {
                    backdrop-filter: blur(10px);
                }
                '''
            },
            {
                'name': 'Portfolio de Estudiante',
                'description': 'Plantilla para portfolios y presentaciones de trabajos estudiantiles',
                'template_type': 'student_portfolio',
                'theme': 'default',
                'page_format': 'A4',
                'orientation': 'portrait',
                'is_public': True,
                'custom_css': '''
                .slide {
                    border-left: 5px solid #10b981;
                }
                .slide-title {
                    color: #065f46;
                }
                '''
            },
            {
                'name': 'Presentación Minimalista',
                'description': 'Plantilla limpia y minimalista para cualquier tipo de contenido',
                'template_type': 'custom',
                'theme': 'default',
                'page_format': 'A4',
                'orientation': 'landscape',
                'is_public': True,
                'custom_css': '''
                .slide {
                    background: #ffffff;
                    border: 1px solid #e5e7eb;
                }
                .slide-title {
                    color: #374151;
                    font-weight: 300;
                }
                '''
            },
            {
                'name': 'Tema Oscuro Moderno',
                'description': 'Plantilla con tema oscuro para presentaciones modernas',
                'template_type': 'custom',
                'theme': 'dark',
                'page_format': 'A4',
                'orientation': 'landscape',
                'is_public': True,
                'custom_css': '''
                .slide {
                    background: #1f2937;
                    color: #f9fafb;
                }
                .slide-title {
                    color: #60a5fa;
                }
                .music-item {
                    background: linear-gradient(135deg, #374151 0%, #4b5563 100%);
                }
                '''
            }
        ]

        created_count = 0
        for template_data in templates_data:
            template, created = PresentationTemplate.objects.get_or_create(
                name=template_data['name'],
                defaults={
                    **template_data,
                    'created_by': user
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Creada plantilla: {template.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'- Ya existe: {template.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Proceso completado. {created_count} plantillas nuevas creadas.'
            )
        )

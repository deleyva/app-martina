"""
Servicios para generar presentaciones HTML y PDF
"""
import os
import tempfile
from datetime import datetime
from django.conf import settings
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.utils import timezone
from .models import Presentation, PresentationSlide

try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False


class PresentationGenerator:
    """Generador de presentaciones HTML y PDF"""
    
    def __init__(self, presentation):
        self.presentation = presentation
        self.template = presentation.template
    
    def generate_html(self):
        """Genera la presentación en formato HTML"""
        try:
            self.presentation.status = 'generating'
            self.presentation.save()
            
            # Obtener las diapositivas ordenadas
            slides = self.presentation.slides.all().order_by('order')
            
            # Preparar el contexto para el template
            context = {
                'presentation': self.presentation,
                'template': self.template,
                'slides': slides,
                'generated_at': timezone.now(),
                'settings': self.presentation.custom_settings,
            }
            
            # Renderizar el HTML
            html_content = render_to_string(
                f'presentations/templates/{self.template.template_type}.html',
                context
            )
            
            # Guardar el archivo HTML
            filename = f"{self.presentation.title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            html_file = ContentFile(html_content.encode('utf-8'))
            self.presentation.html_file.save(filename, html_file)
            
            self.presentation.status = 'ready'
            self.presentation.generated_at = timezone.now()
            self.presentation.save()
            
            return True, "Presentación HTML generada correctamente"
            
        except Exception as e:
            self.presentation.status = 'error'
            self.presentation.save()
            return False, f"Error generando HTML: {str(e)}"
    
    def generate_pdf(self):
        """Genera la presentación en formato PDF usando WeasyPrint"""
        if not WEASYPRINT_AVAILABLE:
            return False, "WeasyPrint no está disponible. Instala con: pip install weasyprint"
        
        try:
            # Primero generar HTML si no existe
            if not self.presentation.html_file:
                success, message = self.generate_html()
                if not success:
                    return False, message
            
            # Leer el contenido HTML
            self.presentation.html_file.seek(0)
            html_content = self.presentation.html_file.read().decode('utf-8')
            
            # Configurar CSS para impresión
            css_content = self._get_print_css()
            
            # Generar PDF con WeasyPrint
            html_doc = weasyprint.HTML(string=html_content, base_url=settings.STATIC_URL)
            css_doc = weasyprint.CSS(string=css_content)
            
            # Crear archivo temporal para el PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                html_doc.write_pdf(temp_pdf.name, stylesheets=[css_doc])
                
                # Leer el PDF generado
                with open(temp_pdf.name, 'rb') as pdf_file:
                    pdf_content = pdf_file.read()
                
                # Guardar el archivo PDF
                filename = f"{self.presentation.title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                pdf_file_obj = ContentFile(pdf_content)
                self.presentation.pdf_file.save(filename, pdf_file_obj)
                
                # Limpiar archivo temporal
                os.unlink(temp_pdf.name)
            
            return True, "PDF generado correctamente"
            
        except Exception as e:
            return False, f"Error generando PDF: {str(e)}"
    
    def _get_print_css(self):
        """Genera CSS optimizado para impresión"""
        page_format = self.template.page_format
        orientation = self.template.orientation
        
        css = f"""
        @page {{
            size: {page_format} {orientation};
            margin: 2cm;
        }}
        
        body {{
            font-family: 'Arial', sans-serif;
            font-size: 12pt;
            line-height: 1.4;
            color: #333;
        }}
        
        .slide {{
            page-break-after: always;
            min-height: 80vh;
            padding: 1cm;
        }}
        
        .slide:last-child {{
            page-break-after: avoid;
        }}
        
        .slide-title {{
            font-size: 18pt;
            font-weight: bold;
            margin-bottom: 1cm;
            color: #2c3e50;
        }}
        
        .music-item {{
            margin-bottom: 1.5cm;
            border-left: 3px solid #3498db;
            padding-left: 0.5cm;
        }}
        
        .music-item-title {{
            font-size: 14pt;
            font-weight: bold;
            margin-bottom: 0.5cm;
        }}
        
        .exercise {{
            background-color: #f8f9fa;
            padding: 0.5cm;
            border-radius: 0.2cm;
            margin: 0.5cm 0;
        }}
        
        .notes {{
            font-style: italic;
            color: #666;
            margin-top: 0.5cm;
        }}
        
        img {{
            max-width: 100%;
            height: auto;
        }}
        
        /* Ocultar elementos no necesarios para impresión */
        .no-print {{
            display: none !important;
        }}
        """
        
        # Añadir CSS personalizado de la plantilla
        if self.template.custom_css:
            css += "\n" + self.template.custom_css
        
        return css


class SlideGenerator:
    """Generador automático de diapositivas"""
    
    @staticmethod
    def generate_slides_from_class_session(presentation, class_session):
        """Genera diapositivas automáticamente desde una sesión de clase"""
        slides_created = []
        order = 0
        
        # Diapositiva de título
        title_slide = PresentationSlide.objects.create(
            presentation=presentation,
            order=order,
            title=class_session.title,
            slide_type='title',
            text_content=f"Fecha: {class_session.date}\nCurso: {class_session.course.name}"
        )
        slides_created.append(title_slide)
        order += 1
        
        # Diapositiva de objetivos si existen
        if hasattr(class_session, 'objectives') and class_session.objectives:
            objectives_slide = PresentationSlide.objects.create(
                presentation=presentation,
                order=order,
                title="Objetivos de la Sesión",
                slide_type='content',
                text_content=class_session.objectives
            )
            slides_created.append(objectives_slide)
            order += 1
        
        # Diapositivas para cada elemento musical
        if hasattr(class_session, 'content_items'):
            for session_content in class_session.sessioncontent_set.all().order_by('order'):
                music_slide = PresentationSlide.objects.create(
                    presentation=presentation,
                    order=order,
                    title=session_content.music_item.title,
                    slide_type='music_item',
                    content_type=ContentType.objects.get_for_model(session_content.music_item),
                    object_id=session_content.music_item.id,
                    text_content=session_content.notes,
                    duration=session_content.estimated_duration,
                    notes=f"Tipo de actividad: {session_content.get_activity_type_display() if hasattr(session_content, 'activity_type') else 'No especificado'}"
                )
                slides_created.append(music_slide)
                order += 1
        
        return slides_created
    
    @staticmethod
    def generate_slides_from_music_collection(presentation, music_items):
        """Genera diapositivas desde una colección de elementos musicales"""
        slides_created = []
        order = 0
        
        # Diapositiva de título
        title_slide = PresentationSlide.objects.create(
            presentation=presentation,
            order=order,
            title=presentation.title,
            slide_type='title',
            text_content=f"Colección musical\nGenerada: {timezone.now().strftime('%d/%m/%Y')}"
        )
        slides_created.append(title_slide)
        order += 1
        
        # Diapositiva para cada elemento musical
        for music_item in music_items:
            music_slide = PresentationSlide.objects.create(
                presentation=presentation,
                order=order,
                title=music_item.title,
                slide_type='music_item',
                content_type=ContentType.objects.get_for_model(music_item),
                object_id=music_item.id,
            )
            slides_created.append(music_slide)
            order += 1
        
        return slides_created


def create_presentation_from_class_session(class_session, template, user, title=None):
    """
    Función de conveniencia para crear una presentación desde una sesión de clase
    """
    from django.contrib.contenttypes.models import ContentType
    
    if not title:
        title = f"Presentación: {class_session.title}"
    
    # Crear la presentación
    presentation = Presentation.objects.create(
        title=title,
        template=template,
        source_content_type=ContentType.objects.get_for_model(class_session),
        source_object_id=class_session.id,
        created_by=user
    )
    
    # Generar diapositivas automáticamente
    slides = SlideGenerator.generate_slides_from_class_session(presentation, class_session)
    
    return presentation, slides


def create_presentation_from_music_items(music_items, template, user, title=None):
    """
    Función de conveniencia para crear una presentación desde elementos musicales
    """
    if not title:
        title = f"Colección Musical - {len(music_items)} elementos"
    
    # Crear la presentación (usando el primer music_item como fuente)
    first_item = music_items[0] if music_items else None
    if not first_item:
        raise ValueError("Se necesita al menos un elemento musical")
    
    presentation = Presentation.objects.create(
        title=title,
        template=template,
        source_content_type=ContentType.objects.get_for_model(first_item),
        source_object_id=first_item.id,
        created_by=user
    )
    
    # Generar diapositivas automáticamente
    slides = SlideGenerator.generate_slides_from_music_collection(presentation, music_items)
    
    return presentation, slides

from django import forms
from .submission_models import ClassroomSubmission, SubmissionVideo, SubmissionImage


class ClassroomSubmissionForm(forms.ModelForm):
    class Meta:
        model = ClassroomSubmission
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 
                                           'placeholder': 'Añade cualquier comentario o explicación sobre tu entrega...'}),
        }
        labels = {
            'notes': 'Notas adicionales',
        }


class VideoUploadForm(forms.ModelForm):
    class Meta:
        model = SubmissionVideo
        fields = ['video']
        widgets = {
            'video': forms.FileInput(attrs={'class': 'form-control', 'accept': 'video/*'}),
        }
        labels = {
            'video': 'Vídeo',
        }

    def clean_video(self):
        video = self.cleaned_data.get('video')
        if video:
            # Check file extension
            valid_extensions = ['mp4', 'mov', 'avi', 'wmv', 'mkv', 'm4v']
            extension = video.name.split('.')[-1].lower()
            if extension not in valid_extensions:
                raise forms.ValidationError('Formato de archivo no válido. Por favor, sube un archivo de vídeo en formato mp4, mov, avi, wmv, mkv o m4v.')
            
            # Check file size (limit to 500MB)
            if video.size > 500 * 1024 * 1024:  # 500MB
                raise forms.ValidationError('El archivo es demasiado grande. El tamaño máximo permitido es 500MB.')
        
        return video


class ImageUploadForm(forms.ModelForm):
    class Meta:
        model = SubmissionImage
        fields = ['image']
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
        labels = {
            'image': 'Imagen',
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # Check file extension
            valid_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
            extension = image.name.split('.')[-1].lower()
            if extension not in valid_extensions:
                raise forms.ValidationError('Formato de archivo no válido. Por favor, sube una imagen en formato jpg, jpeg, png, gif, bmp o webp.')
            
            # Check file size (limit to 10MB)
            if image.size > 10 * 1024 * 1024:  # 10MB
                raise forms.ValidationError('La imagen es demasiado grande. El tamaño máximo permitido es 10MB.')
        
        return image

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, View
from django.conf import settings

User = get_user_model()

class SuperuserRequiredMixin(UserPassesTestMixin):
    """Mixin que verifica que el usuario es superusuario."""
    
    def test_func(self):
        return self.request.user.is_superuser


class ImpersonateUserListView(SuperuserRequiredMixin, ListView):
    """Vista que muestra la lista de usuarios disponibles para impersonar."""
    
    model = User
    template_name = "users/impersonation/user_list.html"
    context_object_name = "users"
    
    def get_queryset(self):
        # Excluimos al usuario actual de la lista
        return User.objects.exclude(id=self.request.user.id).order_by('email')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Impersonar Usuario")
        return context


class ImpersonateUserView(SuperuserRequiredMixin, View):
    """Vista que maneja la impersonación de un usuario."""
    
    def get(self, request, *args, **kwargs):
        user_id = kwargs.get('user_id')
        user = get_object_or_404(User, id=user_id)
        
        # Guardar el ID del superusuario original en la sesión
        request.session['impersonator_id'] = request.user.id
        
        # Iniciar sesión como el usuario seleccionado
        # Especificamos el backend explícitamente para evitar el error de múltiples backends
        backend = settings.AUTHENTICATION_BACKENDS[0]  # Usamos el primer backend configurado
        user.backend = backend
        login(request, user)
        
        messages.success(
            request,
            _(f"Ahora estás impersonando a {user.email}. Para volver a tu cuenta, haz clic en 'Terminar impersonación'.")
        )
        
        return redirect('users:impersonate-return')


class ReturnFromImpersonationView(View):
    """Vista para mostrar página de confirmación para terminar impersonación."""
    
    def get(self, request, *args, **kwargs):
        if 'impersonator_id' in request.session:
            original_user_id = request.session['impersonator_id']
            original_user = User.objects.get(id=original_user_id)
            context = {
                'original_user': original_user,
                'current_user': request.user,
            }
            return render(request, 'users/impersonation/return_confirmation.html', context)
        return redirect('users:redirect')


class EndImpersonationView(View):
    """Vista que finaliza la impersonación y devuelve al usuario original."""
    
    def get(self, request, *args, **kwargs):
        if 'impersonator_id' in request.session:
            original_user_id = request.session['impersonator_id']
            original_user = User.objects.get(id=original_user_id)
            
            # Iniciar sesión como el superusuario original
            # Especificamos el backend explícitamente
            backend = settings.AUTHENTICATION_BACKENDS[0]  # Usamos el primer backend configurado
            original_user.backend = backend
            login(request, original_user)
            
            # Eliminar la información de impersonación de la sesión
            del request.session['impersonator_id']
            
            messages.success(
                request,
                _("Has vuelto a tu cuenta original.")
            )
            
        return redirect('users:redirect')

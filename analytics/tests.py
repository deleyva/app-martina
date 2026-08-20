import json
import uuid

from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client, TestCase
from django.urls import reverse

from martina_bescos_app.middleware import AppModeMiddleware

from .models import Interaction, PageVisit, UserSession


def payload(event_type, visitor_id=None, **extra):
    data = {
        'event_type': event_type,
        'url': 'http://testserver/home/',
        'visitor_id': visitor_id or str(uuid.uuid4()),
    }
    data.update(extra)
    return json.dumps(data)


class AnalyticsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.track_url = reverse('analytics:track_activity')

    def post(self, body):
        return self.client.post(
            self.track_url, body, content_type='application/json'
        )

    def test_pageview_tracking(self):
        response = self.post(payload('pageview'))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(UserSession.objects.count(), 1)
        self.assertEqual(PageVisit.objects.count(), 1)
        self.assertEqual(PageVisit.objects.first().url, 'http://testserver/home/')

    def test_interaction_tracking(self):
        visitor = str(uuid.uuid4())
        self.post(payload('pageview', visitor_id=visitor))

        response = self.post(payload(
            'interaction',
            visitor_id=visitor,
            target_element='button#submit',
            target_text='Submit',
            x=100,
            y=200,
        ))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(Interaction.objects.count(), 1)
        interaction = Interaction.objects.first()
        self.assertEqual(interaction.target_element, 'button#submit')
        self.assertEqual(interaction.visit.url, 'http://testserver/home/')

    def test_same_visitor_reuses_one_row(self):
        visitor = str(uuid.uuid4())
        self.post(payload('pageview', visitor_id=visitor))
        self.post(payload('pageview', visitor_id=visitor))

        self.assertEqual(UserSession.objects.count(), 1)
        self.assertEqual(PageVisit.objects.count(), 2)


class VisitorIdentityTests(TestCase):
    """C9.5 — la identidad de analítica es propia, validada y compatible."""

    def setUp(self):
        self.client = Client()
        self.track_url = reverse('analytics:track_activity')

    def post_raw(self, body):
        return self.client.post(
            self.track_url, json.dumps(body), content_type='application/json'
        )

    def test_legacy_session_key_field_still_accepted(self):
        """El JS viejo cacheado manda `session_key`; debe seguir midiendo."""
        response = self.post_raw({
            'event_type': 'pageview',
            'url': 'http://testserver/home/',
            'session_key': str(uuid.uuid4()),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserSession.objects.count(), 1)

    def test_missing_visitor_id_is_ignored_without_creating_rows(self):
        response = self.post_raw({
            'event_type': 'pageview',
            'url': 'http://testserver/home/',
        })
        self.assertEqual(response.status_code, 202)
        self.assertEqual(UserSession.objects.count(), 0)
        self.assertEqual(PageVisit.objects.count(), 0)

    def test_garbage_visitor_id_is_ignored(self):
        for garbage in ['../../etc/passwd', 'x' * 200, '', 12345, None]:
            with self.subTest(garbage=garbage):
                response = self.post_raw({
                    'event_type': 'pageview',
                    'url': 'http://testserver/home/',
                    'visitor_id': garbage,
                })
                self.assertEqual(response.status_code, 202)
        self.assertEqual(UserSession.objects.count(), 0)


class TelemetryDoesNotTouchSessionTests(TestCase):
    """
    C9.2 y C9.3 — el corazón del bug de login con Google.

    La telemetría llegaba a reescribir la cookie de sesión y a borrar el
    `state` que allauth guarda entre el redirect a Google y el callback.
    """

    def setUp(self):
        self.client = Client()
        self.track_url = reverse('analytics:track_activity')

    def test_tracking_does_not_issue_a_session_cookie(self):
        response = self.client.post(
            self.track_url,
            payload('pageview'),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(settings.SESSION_COOKIE_NAME, response.cookies)

    def test_tracking_does_not_rotate_an_existing_session(self):
        session = self.client.session
        session['marker'] = 'no me toques'
        session.save()
        key_before = session.session_key

        self.client.post(
            self.track_url,
            payload('pageview'),
            content_type='application/json',
        )

        self.assertEqual(self.client.session.session_key, key_before)
        self.assertEqual(self.client.session['marker'], 'no me toques')

    def test_oauth_state_survives_a_tracking_request(self):
        """La regresión exacta: `socialaccount_states` sigue ahí después."""
        session = self.client.session
        session['socialaccount_states'] = {
            'a1b2c3d4e5f6g7h8': [{'process': 'login'}, 1755626961.0]
        }
        session.save()
        key_before = session.session_key

        self.client.post(
            self.track_url,
            payload('pageview'),
            content_type='application/json',
        )

        after = self.client.session
        self.assertEqual(after.session_key, key_before)
        self.assertIn('a1b2c3d4e5f6g7h8', after['socialaccount_states'])

    def test_tracking_performs_no_session_write_at_all(self):
        """
        La claim que de verdad cierra el bug.

        La carrera que borraba el `state` de OAuth no se puede reproducir con un
        cliente de test secuencial: hace falta que dos peticiones concurrentes
        carguen la misma sesión y la guarden entera. Lo que sí es comprobable, y
        es la condición necesaria, es que la petición de telemetría **no escriba
        en la sesión**: sin escritura no hay read-modify-write, y sin eso no hay
        carrera posible.

        Sobre el código anterior esto falla: `AppModeMiddleware` metía
        `app_mode='main'` en cada POST a `/analytics/track/`.
        """
        session = self.client.session
        session['socialaccount_states'] = {'abc': [{'process': 'login'}, 1.0]}
        session.save()
        row_before = SessionStore(session_key=session.session_key).load()

        self.client.post(
            self.track_url,
            payload('pageview'),
            content_type='application/json',
        )

        row_after = SessionStore(session_key=session.session_key).load()
        self.assertNotIn('app_mode', row_after)
        self.assertEqual(row_before, row_after)


class AppModeMiddlewareTests(TestCase):
    """C9.4 — el modo solo se escribe cuando cambia de verdad."""

    def setUp(self):
        self.middleware = AppModeMiddleware(lambda request: None)

    def test_non_navigational_paths_never_decide_the_mode(self):
        for path in ['/analytics/track/', '/static/js/app.js', '/media/x.png']:
            with self.subTest(path=path):
                self.assertIsNone(self.middleware.mode_for_path(path))

    def test_shared_views_preserve_the_existing_mode(self):
        for path in ['/accounts/login/', '/users/84/', '/admin/']:
            with self.subTest(path=path):
                self.assertIsNone(self.middleware.mode_for_path(path))

    def test_incidencias_and_default(self):
        self.assertEqual(
            self.middleware.mode_for_path('/incidencias/listado/'), 'incidencias'
        )
        self.assertEqual(self.middleware.mode_for_path('/my-library/'), 'main')

    def test_default_mode_is_never_persisted(self):
        session = SessionStore()
        self.middleware._remember(session, 'main')
        self.assertNotIn('app_mode', session)
        self.assertFalse(session.modified)

    def test_repeated_incidencias_writes_only_once(self):
        session = SessionStore()
        self.middleware._remember(session, 'incidencias')
        self.assertTrue(session.modified)

        session.modified = False
        self.middleware._remember(session, 'incidencias')
        self.assertFalse(session.modified)

    def test_leaving_incidencias_clears_the_key(self):
        session = SessionStore()
        self.middleware._remember(session, 'incidencias')
        self.middleware._remember(session, 'main')
        self.assertNotIn('app_mode', session)

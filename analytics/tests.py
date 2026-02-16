from django.test import TestCase, Client
from django.urls import reverse
from .models import UserSession, PageVisit, Interaction
import json

class AnalyticsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.track_url = reverse('track_activity')

    def test_pageview_tracking(self):
        data = {
            'event_type': 'pageview',
            'url': 'http://testserver/home/',
        }
        response = self.client.post(
            self.track_url,
            json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.assertEqual(UserSession.objects.count(), 1)
        self.assertEqual(PageVisit.objects.count(), 1)
        self.assertEqual(PageVisit.objects.first().url, 'http://testserver/home/')

    def test_interaction_tracking(self):
        # First create a pageview
        session = self.client.session
        session.create()
        session.save()
        
        # Manually create the session/visit to simulate previous pageview
        # But efficiently we can just call the endpoint twice
        
        data_pv = {
            'event_type': 'pageview',
            'url': 'http://testserver/home/',
        }
        self.client.post(self.track_url, json.dumps(data_pv), content_type='application/json')
        
        data_click = {
            'event_type': 'interaction',
            'target_element': 'button#submit',
            'target_text': 'Submit',
            'x': 100,
            'y': 200
        }
        response = self.client.post(
            self.track_url,
            json.dumps(data_click),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.assertEqual(Interaction.objects.count(), 1)
        interaction = Interaction.objects.first()
        self.assertEqual(interaction.target_element, 'button#submit')
        self.assertEqual(interaction.visit.url, 'http://testserver/home/')

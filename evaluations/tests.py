from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal

from .models import (
    EvaluationItem,
    Student,
    RubricCategory,
    Evaluation,
    RubricScore,
    PendingEvaluationStatus,
)

User = get_user_model()


class ModelTests(TestCase):
    def setUp(self):
        # Create test users
        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="password123",
            name="Teacher",
            is_staff=True,
        )
        self.student_user = User.objects.create_user(
            email="student@example.com",
            password="password123",
            name="Test Student",
        )
        
        # Create evaluation item
        self.evaluation_item = EvaluationItem.objects.create(
            name="Test Evaluation",
            term="primera",
            description="Test description",
        )
        
        # Create student
        self.student = Student.objects.create(
            user=self.student_user,
            group="1A",
        )
        
        # Create rubric categories
        self.category1 = RubricCategory.objects.create(
            name="Plasticidad",
            description="Capacidad de adaptación",
            max_points=2.0,
            order=1,
            evaluation_item=self.evaluation_item,
        )
        
        self.category2 = RubricCategory.objects.create(
            name="Velocidad",
            description="Velocidad de ejecución",
            max_points=2.0,
            order=2,
            evaluation_item=self.evaluation_item,
        )

    def test_evaluation_item_creation(self):
        self.assertEqual(self.evaluation_item.name, "Test Evaluation")
        self.assertEqual(self.evaluation_item.term, "primera")
        self.assertEqual(str(self.evaluation_item), "Test Evaluation")

    def test_student_creation(self):
        self.assertEqual(self.student.group, "1A")
        self.assertEqual(str(self.student), "Test Student")
        
    def test_rubric_category_creation(self):
        self.assertEqual(self.category1.name, "Plasticidad")
        self.assertEqual(self.category1.max_points, 2.0)
        self.assertEqual(str(self.category1), "Plasticidad")
        
    def test_evaluation_creation_and_score_calculation(self):
        # Create evaluation
        evaluation = Evaluation.objects.create(
            student=self.student,
            evaluation_item=self.evaluation_item,
            score=8.5,
            max_score=10.0,
        )
        
        # Add rubric scores
        RubricScore.objects.create(
            evaluation=evaluation,
            category=self.category1,
            points=1.5,
        )
        
        RubricScore.objects.create(
            evaluation=evaluation,
            category=self.category2,
            points=2.0,
        )
        
        # Test score calculation
        calculated_score = evaluation.calculate_score()
        expected_score = (1.5 + 2.0) / (2.0 + 2.0) * 10  # (3.5/4) * 10 = 8.75
        self.assertAlmostEqual(calculated_score, 8.75)
        
    def test_pending_evaluation_status(self):
        # Create pending evaluation
        pending = PendingEvaluationStatus.objects.create(
            student=self.student,
            evaluation_item=self.evaluation_item,
            classroom_submission=False,
        )
        
        self.assertEqual(pending.student, self.student)
        self.assertEqual(pending.evaluation_item, self.evaluation_item)
        self.assertFalse(pending.classroom_submission)
        
        # Test get_pending_students method
        pending_students = PendingEvaluationStatus.get_pending_students(
            evaluation_item=self.evaluation_item,
            group="1A",
            include_classroom=False,
        )
        
        self.assertEqual(pending_students.count(), 1)
        
        # Test filtering with classroom submissions
        pending.classroom_submission = True
        pending.save()
        
        pending_students = PendingEvaluationStatus.get_pending_students(
            evaluation_item=self.evaluation_item,
            include_classroom=False,
        )
        
        self.assertEqual(pending_students.count(), 0)
        
        pending_students = PendingEvaluationStatus.get_pending_students(
            evaluation_item=self.evaluation_item,
            include_classroom=True,
        )
        
        self.assertEqual(pending_students.count(), 1)


class ViewTests(TestCase):
    def setUp(self):
        # Create test users
        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="password123",
            name="Teacher",
            is_staff=True,
        )
        self.student_user = User.objects.create_user(
            email="student@example.com",
            password="password123",
            name="Test Student",
        )
        
        # Create evaluation item
        self.evaluation_item = EvaluationItem.objects.create(
            name="Test Evaluation",
            term="primera",
            description="Test description",
        )
        
        # Create student
        self.student = Student.objects.create(
            user=self.student_user,
            group="1A",
        )
        
        # Create rubric categories
        self.category1 = RubricCategory.objects.create(
            name="Plasticidad",
            description="Capacidad de adaptación",
            max_points=2.0,
            order=1,
            evaluation_item=self.evaluation_item,
        )
        
        self.category2 = RubricCategory.objects.create(
            name="Velocidad",
            description="Velocidad de ejecución",
            max_points=2.0,
            order=2,
            evaluation_item=self.evaluation_item,
        )
        
        # Create pending evaluation
        self.pending = PendingEvaluationStatus.objects.create(
            student=self.student,
            evaluation_item=self.evaluation_item,
            classroom_submission=False,
        )
        
        # Set up client
        self.client = Client()
        self.client.login(email="teacher@example.com", password="password123")
    
    def test_evaluation_item_list_view(self):
        response = self.client.get(reverse('evaluations:evaluation_item_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'evaluations/item_list.html')
        self.assertContains(response, "Test Evaluation")
    
    def test_pending_evaluations_view(self):
        url = reverse('evaluations:pending_evaluations')
        response = self.client.get(f"{url}?evaluation_item={self.evaluation_item.id}")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'evaluations/pending_evaluations.html')
        self.assertContains(response, "Test Student")
        
        # Test with classroom filter
        response = self.client.get(f"{url}?evaluation_item={self.evaluation_item.id}&show_classroom=true")
        self.assertEqual(response.status_code, 200)
        
        # Change to classroom submission
        self.pending.classroom_submission = True
        self.pending.save()
        
        # Test without classroom filter should not show the student
        response = self.client.get(f"{url}?evaluation_item={self.evaluation_item.id}")
        self.assertNotContains(response, "Test Student")
        
        # Test with classroom filter should show the student
        response = self.client.get(f"{url}?evaluation_item={self.evaluation_item.id}&show_classroom=true")
        self.assertContains(response, "Test Student")
    
    def test_toggle_classroom_submission(self):
        url = reverse('evaluations:toggle_classroom_submission', args=[self.student.id])
        
        # Toggle to true
        response = self.client.post(url, {
            'evaluation_item_id': self.evaluation_item.id,
            'is_checked': 'true'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 200)
        
        # Verify the change
        self.pending.refresh_from_db()
        self.assertTrue(self.pending.classroom_submission)
        
        # Toggle back to false
        response = self.client.post(url, {
            'evaluation_item_id': self.evaluation_item.id,
            'is_checked': 'false'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 200)
        
        # Verify the change
        self.pending.refresh_from_db()
        self.assertFalse(self.pending.classroom_submission)


class HtmxViewTests(TestCase):
    def setUp(self):
        # Create test users
        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="password123",
            name="Teacher",
            is_staff=True,
        )
        self.student_user = User.objects.create_user(
            email="student@example.com",
            password="password123",
            name="Test Student",
        )
        
        # Create evaluation item
        self.evaluation_item = EvaluationItem.objects.create(
            name="Test Evaluation",
            term="primera",
            description="Test description",
        )
        
        # Create student
        self.student = Student.objects.create(
            user=self.student_user,
            group="1A",
        )
        
        # Create rubric categories
        self.category1 = RubricCategory.objects.create(
            name="Plasticidad",
            description="Capacidad de adaptación",
            max_points=2.0,
            order=1,
            evaluation_item=self.evaluation_item,
        )
        
        # Create pending evaluation
        self.pending = PendingEvaluationStatus.objects.create(
            student=self.student,
            evaluation_item=self.evaluation_item,
            classroom_submission=False,
        )
        
        # Set up client
        self.client = Client()
        self.client.login(email="teacher@example.com", password="password123")
    
    def test_search_student_htmx(self):
        # La vista search_students espera 'query', no 'q', y necesita al menos 3 caracteres
        url = reverse('evaluations:search_students') 
        response = self.client.get(f"{url}?query=Test", HTTP_HX_REQUEST='true')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Student")
    
    def test_save_evaluation_htmx(self):
        url = reverse('evaluations:save_evaluation', args=[self.student.id])
        
        # HTMX save evaluation request con los parámetros que espera la vista
        data = {
            'evaluation_item_id': self.evaluation_item.id,
            'direct_score': '8.5',  # La vista espera direct_score, no score
            f'category_{self.category1.id}': '1.5',  # Formato correcto: category_{id}, no rubric_score_{id}
            'max_score': '10.0',  # Opcional pero bueno incluirlo
            'classroom_submission': 'off',  # Para indicar si es entrega por classroom
        }
        
        response = self.client.post(
            url, 
            data=data,
            HTTP_HX_REQUEST='true'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify evaluation was created
        evaluation = Evaluation.objects.filter(
            student=self.student,
            evaluation_item=self.evaluation_item
        ).first()
        
        self.assertIsNotNone(evaluation)
        self.assertEqual(evaluation.score, Decimal('8.5'))
        
        # Verify rubric score was created
        rubric_score = RubricScore.objects.filter(
            evaluation=evaluation,
            category=self.category1
        ).first()
        
        self.assertIsNotNone(rubric_score)
        self.assertEqual(rubric_score.points, Decimal('1.5'))

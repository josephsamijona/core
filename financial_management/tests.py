from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Budget, Revenue ,FinancialRecord,Expense,Invoice
from datetime import date, timedelta
from .financial_reports import (
    generate_budget_report,
    generate_revenue_expense_report,
    generate_financial_health_report,
    generate_cash_flow_report
)

User = get_user_model()

class BudgetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.client.force_authenticate(user=self.user)
        
        self.budget_data = {
            'name': 'Test Budget',
            'type': 'annual',
            'start_date': '2023-01-01',
            'end_date': '2023-12-31',
            'total_amount': '10000.00',
        }
        
        self.budget = Budget.objects.create(
            name='Existing Budget',
            type='monthly',
            start_date='2023-06-01',
            end_date='2023-06-30',
            total_amount=5000.00,
            remaining_amount=5000.00,
            created_by=self.user
        )

    def test_create_budget(self):
        url = reverse('budget-list')
        response = self.client.post(url, self.budget_data, format='json')
        print(f"Response status code: {response.status_code}")
        print(f"Response data: {response.data}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Budget.objects.count(), 2)
        self.assertEqual(Budget.objects.latest('id').name, 'Test Budget')

    def test_list_budgets(self):
        url = reverse('budget-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_budget(self):
        url = reverse('budget-detail', kwargs={'pk': self.budget.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Existing Budget')

    def test_update_budget(self):
        url = reverse('budget-detail', kwargs={'pk': self.budget.id})
        updated_data = {
            'name': 'Updated Budget',
            'total_amount': '6000.00'
        }
        response = self.client.patch(url, updated_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.name, 'Updated Budget')
        self.assertEqual(self.budget.total_amount, 6000.00)
        self.assertEqual(self.budget.remaining_amount, 6000.00)

    def test_delete_budget(self):
        url = reverse('budget-detail', kwargs={'pk': self.budget.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Budget.objects.count(), 0)

    def test_budget_status(self):
        url = reverse('budget-budget-status', kwargs={'pk': self.budget.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_amount'], 5000.00)
        self.assertEqual(response.data['remaining_amount'], 5000.00)
        self.assertEqual(response.data['spent_amount'], 0)
        self.assertEqual(response.data['percentage_used'], 0)

    def test_record_expense(self):
        url = reverse('budget-record-expense', kwargs={'pk': self.budget.id})
        response = self.client.post(url, {'amount': 1000}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.remaining_amount, 4000.00)

    def test_record_expense_insufficient_funds(self):
        url = reverse('budget-record-expense', kwargs={'pk': self.budget.id})
        response = self.client.post(url, {'amount': 6000}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.remaining_amount, 5000.00)
        
        
class RevenueTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.client.force_authenticate(user=self.user)
        
        self.revenue_data = {
            'source': 'ticket_sales',
            'amount': '1000.00',
            'date': '2023-01-01',
            'description': 'Test revenue'
        }
        
        self.revenue = Revenue.objects.create(
            source='subscription',
            amount=500.00,
            date='2023-01-15',
            description='Existing revenue',
            recorded_by=self.user
        )

    def test_create_revenue(self):
        url = reverse('revenue-list')
        response = self.client.post(url, self.revenue_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Revenue.objects.count(), 2)
        self.assertEqual(Revenue.objects.latest('id').source, 'ticket_sales')

    def test_list_revenues(self):
        url = reverse('revenue-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_revenue(self):
        url = reverse('revenue-detail', kwargs={'pk': self.revenue.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['source'], 'subscription')

    def test_update_revenue(self):
        url = reverse('revenue-detail', kwargs={'pk': self.revenue.id})
        updated_data = {
            'amount': '600.00'
        }
        response = self.client.patch(url, updated_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.revenue.refresh_from_db()
        self.assertEqual(self.revenue.amount, 600.00)

    def test_delete_revenue(self):
        url = reverse('revenue-detail', kwargs={'pk': self.revenue.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Revenue.objects.count(), 0)

    def test_revenue_by_source(self):
        url = reverse('revenue-by-source')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['source'], 'subscription')
        self.assertEqual(response.data[0]['total'], '500.00')

    def test_revenue_by_period(self):
        url = reverse('revenue-by-period')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['month'], '2023-01-01')
        self.assertEqual(response.data[0]['total'], '500.00')

    def test_revenue_by_source_and_period(self):
        url = reverse('revenue-by-source-and-period')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['month'], '2023-01-01')
        self.assertEqual(response.data[0]['source'], 'subscription')
        self.assertEqual(response.data[0]['total'], '500.00')
        
        
class ExpenseTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.client.force_authenticate(user=self.user)
        
        self.expense_data = {
            'category': 'fuel',
            'amount': '100.00',
            'date': '2023-01-01',
            'description': 'Test expense'
        }
        
        self.expense = Expense.objects.create(
            category='maintenance',
            amount=500.00,
            date='2023-01-15',
            description='Existing expense',
            recorded_by=self.user
        )

    def test_create_expense(self):
        url = reverse('expense-list')
        response = self.client.post(url, self.expense_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Expense.objects.count(), 2)
        self.assertEqual(Expense.objects.latest('id').category, 'fuel')

    def test_approve_expense(self):
        url = reverse('expense-approve', kwargs={'pk': self.expense.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.approval_status, 'approved')

    def test_reject_expense(self):
        url = reverse('expense-reject', kwargs={'pk': self.expense.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.approval_status, 'rejected')

    def test_expense_by_category(self):
        url = reverse('expense-by-category')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['category'], 'maintenance')
        self.assertEqual(response.data[0]['total'], '500.00')

    def test_expense_by_period(self):
        url = reverse('expense-by-period')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['month'], '2023-01-01')
        self.assertEqual(response.data[0]['total'], '500.00')

    def test_expense_by_category_and_period(self):
        url = reverse('expense-by-category-and-period')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['month'], '2023-01-01')
        self.assertEqual(response.data[0]['category'], 'maintenance')
        self.assertEqual(response.data[0]['total'], '500.00')
        
class FinancialRecordTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.client.force_authenticate(user=self.user)
        
        self.budget = Budget.objects.create(
            name='Test Budget',
            type='annual',
            start_date='2023-01-01',
            end_date='2023-12-31',
            total_amount=10000.00,
            remaining_amount=10000.00,
            created_by=self.user
        )
        
        self.record_data = {
            'record_type': 'income',
            'amount': '1000.00',
            'date': '2023-01-01',
            'description': 'Test record',
            'related_budget': self.budget.id
        }
        
        self.record = FinancialRecord.objects.create(
            record_type='expense',
            amount=500.00,
            date='2023-01-15',
            description='Existing record',
            related_budget=self.budget,
            created_by=self.user
        )

    def test_create_record(self):
        url = reverse('financialrecord-list')
        response = self.client.post(url, self.record_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FinancialRecord.objects.count(), 2)
        self.assertEqual(FinancialRecord.objects.latest('id').record_type, 'income')

    def test_list_records(self):
        url = reverse('financialrecord-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_record(self):
        url = reverse('financialrecord-detail', kwargs={'pk': self.record.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['record_type'], 'expense')

    def test_update_record(self):
        url = reverse('financialrecord-detail', kwargs={'pk': self.record.id})
        updated_data = {
            'amount': '600.00'
        }
        response = self.client.patch(url, updated_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.record.refresh_from_db()
        self.assertEqual(self.record.amount, 600.00)

    def test_delete_record(self):
        url = reverse('financialrecord-detail', kwargs={'pk': self.record.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(FinancialRecord.objects.count(), 0)

    def test_records_by_type(self):
        url = reverse('financialrecord-by-type')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['type'], 'expense')
        self.assertEqual(response.data[0]['total'], '500.00')

    def test_records_by_budget(self):
        url = reverse('financialrecord-by-budget')
        response = self.client.get(url, {'budget_id': self.budget.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['record_type'], 'expense')

    def test_records_by_period(self):
        url = reverse('financialrecord-by-period')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['month'], '2023-01-01')
        self.assertEqual(response.data[0]['type'], 'expense')
        self.assertEqual(response.data[0]['total'], '500.00')
        
class InvoiceTests(TestCase):
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.client.force_authenticate(user=self.user)
        
        self.client_user = User.objects.create_user(username='clientuser', password='12345')
        
        self.invoice_data = {
            'invoice_number': 'INV-001',
            'client': self.client_user.id,
            'client_name_text': '',  # Laissons ce champ vide pour utiliser le nom d'utilisateur
            'issue_date': '2023-01-01',
            'due_date': '2023-01-31',
            'total_amount': '1000.00',
            'status': 'draft',
            'notes': 'Test invoice'
        }
        
        self.invoice = Invoice.objects.create(
            invoice_number='INV-002',
            client=self.client_user,
            client_name_text='',  # Laissons ce champ vide pour utiliser le nom d'utilisateur
            issue_date='2023-02-01',
            due_date='2023-02-28',
            total_amount=2000.00,
            status='sent',
            created_by=self.user
        )

    def test_create_invoice(self):
        url = reverse('invoice-list')
        response = self.client.post(url, self.invoice_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Invoice.objects.count(), 2)
        self.assertEqual(Invoice.objects.latest('id').invoice_number, 'INV-001')
        self.assertEqual(Invoice.objects.latest('id').client, self.client_user)

    def test_list_invoices(self):
        url = reverse('invoice-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_invoice(self):
        url = reverse('invoice-detail', kwargs={'pk': self.invoice.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['invoice_number'], 'INV-002')
        self.assertEqual(response.data['client_name'], 'clientuser')

    def test_update_invoice_status(self):
        url = reverse('invoice-update-status', kwargs={'pk': self.invoice.id})
        response = self.client.post(url, {'status': 'paid'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'paid')

    def test_invoices_by_status(self):
        url = reverse('invoice-by-status')
        response = self.client.get(url, {'status': 'sent'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['invoice_number'], 'INV-002')

    def test_overdue_invoices(self):
        self.invoice.due_date = date.today() - timedelta(days=1)
        self.invoice.save()
        
        Invoice.objects.create(
            invoice_number='INV-003',
            client=self.client_user,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            total_amount=3000.00,
            status='sent',
            created_by=self.user
        )
        
        url = reverse('invoice-overdue')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['invoice_number'], 'INV-002')
        self.assertEqual(response.data[0]['client_name'], 'clientuser')
        

class FinancialReportsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.client.force_authenticate(user=self.user)

        # Créer des données de test
        self.start_date = date.today() - timedelta(days=30)
        self.end_date = date.today()

        # Créer un budget
        self.budget = Budget.objects.create(
            name="Test Budget",
            start_date=self.start_date,
            end_date=self.end_date,
            total_amount=10000,
            remaining_amount=5000,
            created_by=self.user
        )

        # Créer des revenus
        Revenue.objects.create(
            source="Test Revenue",
            amount=5000,
            date=self.start_date + timedelta(days=5),
            recorded_by=self.user
        )

        # Créer des dépenses
        Expense.objects.create(
            category="Test Expense",
            amount=2000,
            date=self.start_date + timedelta(days=10),
            recorded_by=self.user
        )

        # Créer des enregistrements financiers
        FinancialRecord.objects.create(
            record_type="income",
            amount=5000,
            date=self.start_date + timedelta(days=5),
            description="Test Income",
            created_by=self.user
        )
        FinancialRecord.objects.create(
            record_type="expense",
            amount=2000,
            date=self.start_date + timedelta(days=10),
            description="Test Expense",
            created_by=self.user
        )

    def test_generate_budget_report(self):
        report = generate_budget_report(self.start_date, self.end_date)
        self.assertIn('dataframe', report)
        self.assertIn('graph', report)
        self.assertEqual(len(report['dataframe']), 1)
        self.assertEqual(report['dataframe'][0]['name'], "Test Budget")

    def test_generate_revenue_expense_report(self):
        report = generate_revenue_expense_report(self.start_date, self.end_date)
        self.assertIn('revenue_data', report)
        self.assertIn('expense_data', report)
        self.assertIn('graph', report)
        self.assertEqual(len(report['revenue_data']), 1)
        self.assertEqual(len(report['expense_data']), 1)
        self.assertIsNotNone(report['graph'])

    def test_generate_financial_health_report(self):
        report = generate_financial_health_report()
        self.assertIn('total_revenue', report)
        self.assertIn('total_expense', report)
        self.assertIn('net_income', report)
        self.assertIn('current_ratio', report)
        self.assertIn('debt_to_equity_ratio', report)

    def test_generate_cash_flow_report(self):
        report = generate_cash_flow_report(self.start_date, self.end_date)
        self.assertIn('dataframe', report)
        self.assertIn('graph', report)
        self.assertEqual(len(report['dataframe']), 2)  # We created 2 financial records

    def test_financial_report_view(self):
        url = reverse('financial-reports')
        response = self.client.get(url, {
            'type': 'all',
            'start_date': self.start_date,
            'end_date': self.end_date
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('budget', response.data)
        self.assertIn('revenue_expense', response.data)
        self.assertIn('financial_health', response.data)
        self.assertIn('cash_flow', response.data)
        self.assertIsNotNone(response.data['budget']['graph'])
        self.assertIsNotNone(response.data['revenue_expense']['graph'])

    def test_financial_report_view_missing_dates(self):
        url = reverse('financial-reports')
        response = self.client.get(url, {'type': 'all'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_financial_report_view_specific_type(self):
        url = reverse('financial-reports')
        response = self.client.get(url, {
            'type': 'budget',
            'start_date': self.start_date,
            'end_date': self.end_date
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('budget', response.data)
        self.assertNotIn('revenue_expense', response.data)
        self.assertNotIn('financial_health', response.data)
        self.assertNotIn('cash_flow', response.data)
        self.assertIsNotNone(response.data['budget']['graph'])

    def test_unauthorized_access(self):
        self.client.force_authenticate(user=None)
        url = reverse('financial-reports')
        response = self.client.get(url, {
            'type': 'all',
            'start_date': self.start_date,
            'end_date': self.end_date
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
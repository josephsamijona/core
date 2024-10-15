from django.shortcuts import render
from rest_framework.views import APIView
from .models import Budget, Revenue ,FinancialRecord,Expense,Invoice
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Budget
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from .serializers import BudgetSerializer, RevenueSerializer, ExpenseSerializer ,FinancialRecordSerializer ,InvoiceSerializer
from .financial_reports import (
    generate_budget_report,
    generate_revenue_expense_report,
    generate_financial_health_report,
    generate_cash_flow_report
)


class BudgetViewSet(viewsets.ModelViewSet):
    queryset = Budget.objects.all()
    serializer_class = BudgetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        new_total = serializer.validated_data.get('total_amount', instance.total_amount)
        if new_total != instance.total_amount:
            difference = new_total - instance.total_amount
            new_remaining = instance.remaining_amount + difference
            serializer.save(remaining_amount=new_remaining)
        else:
            serializer.save()

    @action(detail=True, methods=['get'])
    def budget_status(self, request, pk=None):
        budget = self.get_object()
        return Response({
            'total_amount': budget.total_amount,
            'remaining_amount': budget.remaining_amount,
            'spent_amount': budget.total_amount - budget.remaining_amount,
            'percentage_used': (budget.total_amount - budget.remaining_amount) / budget.total_amount * 100
        })

    @action(detail=True, methods=['post'])
    def record_expense(self, request, pk=None):
        budget = self.get_object()
        amount = request.data.get('amount', 0)
        if amount <= 0:
            return Response({'error': 'Amount must be positive'}, status=status.HTTP_400_BAD_REQUEST)
        if amount > budget.remaining_amount:
            return Response({'error': 'Insufficient budget'}, status=status.HTTP_400_BAD_REQUEST)
        
        budget.remaining_amount -= amount
        budget.save()
        return Response({'message': 'Expense recorded successfully', 'remaining_amount': budget.remaining_amount})
    

class RevenueViewSet(viewsets.ModelViewSet):
    queryset = Revenue.objects.all()
    serializer_class = RevenueSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)

    @action(detail=False, methods=['get'])
    def by_source(self, request):
        revenues = Revenue.objects.values('source').annotate(total=Sum('amount'))
        return Response([{'source': r['source'], 'total': str(r['total'])} for r in revenues])

    @action(detail=False, methods=['get'])
    def by_period(self, request):
        revenues = Revenue.objects.annotate(month=TruncMonth('date')).values('month').annotate(total=Sum('amount')).order_by('month')
        return Response([{'month': r['month'].strftime('%Y-%m-%d'), 'total': str(r['total'])} for r in revenues])

    @action(detail=False, methods=['get'])
    def by_source_and_period(self, request):
        revenues = Revenue.objects.annotate(month=TruncMonth('date')).values('month', 'source').annotate(total=Sum('amount')).order_by('month', 'source')
        return Response([{'month': r['month'].strftime('%Y-%m-%d'), 'source': r['source'], 'total': str(r['total'])} for r in revenues])
    
class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        expense = self.get_object()
        expense.approval_status = 'approved'
        expense.approved_by = request.user
        expense.save()
        return Response({'status': 'expense approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        expense = self.get_object()
        expense.approval_status = 'rejected'
        expense.approved_by = request.user
        expense.save()
        return Response({'status': 'expense rejected'})

    @action(detail=False, methods=['get'])
    def by_category(self, request):
        expenses = Expense.objects.values('category').annotate(total=Sum('amount'))
        return Response([{'category': e['category'], 'total': str(e['total'])} for e in expenses])

    @action(detail=False, methods=['get'])
    def by_period(self, request):
        expenses = Expense.objects.annotate(month=TruncMonth('date')).values('month').annotate(total=Sum('amount')).order_by('month')
        return Response([{'month': e['month'].strftime('%Y-%m-%d'), 'total': str(e['total'])} for e in expenses])

    @action(detail=False, methods=['get'])
    def by_category_and_period(self, request):
        expenses = Expense.objects.annotate(month=TruncMonth('date')).values('month', 'category').annotate(total=Sum('amount')).order_by('month', 'category')
        return Response([{'month': e['month'].strftime('%Y-%m-%d'), 'category': e['category'], 'total': str(e['total'])} for e in expenses])
    
class FinancialRecordViewSet(viewsets.ModelViewSet):
    queryset = FinancialRecord.objects.all()
    serializer_class = FinancialRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        records = FinancialRecord.objects.values('record_type').annotate(total=Sum('amount'))
        return Response([{'type': r['record_type'], 'total': str(r['total'])} for r in records])

    @action(detail=False, methods=['get'])
    def by_budget(self, request):
        budget_id = request.query_params.get('budget_id')
        if not budget_id:
            return Response({'error': 'budget_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            budget = Budget.objects.get(id=budget_id)
        except Budget.DoesNotExist:
            return Response({'error': 'Budget not found'}, status=status.HTTP_404_NOT_FOUND)
        
        records = FinancialRecord.objects.filter(related_budget=budget)
        serializer = self.get_serializer(records, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_period(self, request):
        records = FinancialRecord.objects.annotate(month=TruncMonth('date')).values('month', 'record_type').annotate(total=Sum('amount')).order_by('month', 'record_type')
        return Response([{'month': r['month'].strftime('%Y-%m-%d'), 'type': r['record_type'], 'total': str(r['total'])} for r in records])
    
class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        invoice = self.get_object()
        new_status = request.data.get('status')
        if new_status not in dict(Invoice.STATUS_CHOICES):
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)
        
        invoice.status = new_status
        invoice.save()
        return Response({'status': 'invoice status updated'})

    @action(detail=False, methods=['get'])
    def by_status(self, request):
        status = request.query_params.get('status')
        if status:
            invoices = Invoice.objects.filter(status=status)
        else:
            invoices = Invoice.objects.all()
        serializer = self.get_serializer(invoices, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        today = timezone.now().date()
        overdue_invoices = Invoice.objects.filter(status='sent', due_date__lt=today)
        serializer = self.get_serializer(overdue_invoices, many=True)
        return Response(serializer.data)
    
class FinancialReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        report_type = request.query_params.get('type', 'all')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if not start_date or not end_date:
            return Response({"error": "start_date and end_date are required"}, status=status.HTTP_400_BAD_REQUEST)

        reports = {}

        if report_type in ['budget', 'all']:
            reports['budget'] = generate_budget_report(start_date, end_date)

        if report_type in ['revenue_expense', 'all']:
            reports['revenue_expense'] = generate_revenue_expense_report(start_date, end_date)

        if report_type in ['financial_health', 'all']:
            reports['financial_health'] = generate_financial_health_report()

        if report_type in ['cash_flow', 'all']:
            reports['cash_flow'] = generate_cash_flow_report(start_date, end_date)

        return Response(reports)
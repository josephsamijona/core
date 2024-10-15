import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from django.db.models import Sum
from django.utils import timezone
from .models import Budget, Revenue, Expense, FinancialRecord

def generate_budget_report(start_date, end_date):
    budgets = Budget.objects.filter(start_date__gte=start_date, end_date__lte=end_date)
    data = []
    for budget in budgets:
        spent = budget.total_amount - budget.remaining_amount
        data.append({
            'name': budget.name,
            'total_amount': float(budget.total_amount),
            'spent': float(spent),
            'remaining': float(budget.remaining_amount),
            'percentage_used': (float(spent) / float(budget.total_amount)) * 100 if budget.total_amount else 0
        })
    df = pd.DataFrame(data)
    
    graph = None
    if not df.empty:
        plt.figure(figsize=(10, 6))
        df.plot(kind='bar', x='name', y=['total_amount', 'spent', 'remaining'])
        plt.title('Aperçu des budgets')
        plt.xlabel('Budgets')
        plt.ylabel('Montant')
        plt.legend(['Total', 'Dépensé', 'Restant'])
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        image_png = buffer.getvalue()
        graph = base64.b64encode(image_png)
        graph = graph.decode('utf-8')
        buffer.close()
    
    return {
        'dataframe': df.to_dict('records'),
        'graph': graph
    }

def generate_revenue_expense_report(start_date, end_date):
    revenues = Revenue.objects.filter(date__range=[start_date, end_date]).values('source').annotate(total=Sum('amount'))
    expenses = Expense.objects.filter(date__range=[start_date, end_date]).values('category').annotate(total=Sum('amount'))
    
    revenue_df = pd.DataFrame(revenues)
    expense_df = pd.DataFrame(expenses)
    
    graph = None
    if not revenue_df.empty or not expense_df.empty:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))
        
        if not revenue_df.empty:
            revenue_df['total'] = revenue_df['total'].astype(float)
            revenue_df.plot(kind='pie', y='total', labels=revenue_df['source'], ax=ax1, autopct='%1.1f%%')
            ax1.set_title('Répartition des revenus')
        
        if not expense_df.empty:
            expense_df['total'] = expense_df['total'].astype(float)
            expense_df.plot(kind='pie', y='total', labels=expense_df['category'], ax=ax2, autopct='%1.1f%%')
            ax2.set_title('Répartition des dépenses')
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        image_png = buffer.getvalue()
        graph = base64.b64encode(image_png)
        graph = graph.decode('utf-8')
        buffer.close()
    
    return {
        'revenue_data': revenue_df.to_dict('records'),
        'expense_data': expense_df.to_dict('records'),
        'graph': graph
    }

def generate_financial_health_report():
    current_date = timezone.now().date()
    
    total_revenue = Revenue.objects.aggregate(total=Sum('amount'))['total'] or 0
    total_expense = Expense.objects.aggregate(total=Sum('amount'))['total'] or 0
    net_income = total_revenue - total_expense
    
    current_assets = FinancialRecord.objects.filter(record_type='income', date__lte=current_date).aggregate(total=Sum('amount'))['total'] or 0
    current_liabilities = FinancialRecord.objects.filter(record_type='expense', date__lte=current_date).aggregate(total=Sum('amount'))['total'] or 0
    
    current_ratio = current_assets / current_liabilities if current_liabilities else float('inf')
    debt_to_equity_ratio = current_liabilities / (current_assets - current_liabilities) if (current_assets - current_liabilities) else float('inf')
    
    return {
        'total_revenue': total_revenue,
        'total_expense': total_expense,
        'net_income': net_income,
        'current_assets': current_assets,
        'current_liabilities': current_liabilities,
        'current_ratio': current_ratio,
        'debt_to_equity_ratio': debt_to_equity_ratio
    }

def generate_cash_flow_report(start_date, end_date):
    cash_flows = FinancialRecord.objects.filter(date__range=[start_date, end_date]).order_by('date')
    
    df = pd.DataFrame(list(cash_flows.values()))
    df['cumulative_cash'] = df['amount'].cumsum()
    
    # Générer un graphique
    plt.figure(figsize=(12, 6))
    plt.plot(df['date'], df['cumulative_cash'])
    plt.title('Flux de trésorerie cumulé')
    plt.xlabel('Date')
    plt.ylabel('Montant cumulé')
    
    # Convertir le graphique en image base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    image_png = buffer.getvalue()
    graph = base64.b64encode(image_png)
    graph = graph.decode('utf-8')
    buffer.close()
    
    return {
        'dataframe': df.to_dict('records'),
        'graph': graph
    }
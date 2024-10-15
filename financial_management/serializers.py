from rest_framework import serializers
from .models import Budget, Revenue ,FinancialRecord,Expense,Invoice

class BudgetSerializer(serializers.ModelSerializer):
    spent_amount = serializers.SerializerMethodField(read_only=True)
    percentage_used = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Budget
        fields = ['id', 'name', 'type', 'start_date', 'end_date', 'total_amount', 'remaining_amount', 'spent_amount', 'percentage_used', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at', 'remaining_amount']

    def get_spent_amount(self, obj):
        return obj.total_amount - obj.remaining_amount

    def get_percentage_used(self, obj):
        return (obj.total_amount - obj.remaining_amount) / obj.total_amount * 100 if obj.total_amount else 0

    def create(self, validated_data):
        validated_data['remaining_amount'] = validated_data['total_amount']
        return super().create(validated_data)
    
class RevenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Revenue
        fields = ['id', 'source', 'amount', 'date', 'description', 'recorded_by', 'created_at']
        read_only_fields = ['id', 'recorded_by', 'created_at']

    def create(self, validated_data):
        validated_data['recorded_by'] = self.context['request'].user
        return super().create(validated_data)
    
class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ['id', 'category', 'amount', 'date', 'description', 'approval_status', 'approved_by', 'recorded_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'approved_by', 'recorded_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['recorded_by'] = self.context['request'].user
        return super().create(validated_data)
    
class FinancialRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialRecord
        fields = ['id', 'record_type', 'amount', 'date', 'description', 'related_budget', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
    
class InvoiceSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(read_only=True)

    class Meta:
        model = Invoice
        fields = ['id', 'invoice_number', 'client', 'client_name', 'client_name_text', 'issue_date', 'due_date', 'total_amount', 'status', 'notes', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['client_name'] = instance.client_name
        return representation
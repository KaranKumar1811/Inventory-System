from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import get_object_or_404, redirect, render 
from .forms import ReturnTransactionForm    
from django.utils import timezone
from .models import Transaction, Employee, Uniform, ReturnRecord, TransactionItem, MultiItemTransaction, ItemReturnRecord, SiteLocation

# Inline admin for TransactionItems within a MultiItemTransaction
class TransactionItemInline(admin.TabularInline):
    model = TransactionItem
    extra = 1

    def display_total_cost(self, obj):
        if obj.pk:  # Only calculate if object exists
            return obj.total_cost()
        return "N/A"
    display_total_cost.short_description = "Total Cost"

    def return_button(self, obj):
        if obj.pk and obj.total_returned < obj.quantity:
            url = reverse('admin:transaction_item_return', args=[obj.pk])
            return format_html('<a class="button" href="{}">Return</a>', url)
        elif obj.pk:
            return format_html(
                'Returned: {}/{}',
                obj.total_returned,
                obj.quantity
            )
        return "N/A"
    return_button.short_description = "Return"

    readonly_fields = ('display_total_cost', 'return_button')
    fields = ('uniform', 'quantity', 'display_total_cost', 'return_button')


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    show_change_link = True

    def display_total_cost(self, obj):
        return obj.total_cost()
    display_total_cost.short_description = "Total Cost"

    readonly_fields = ('transaction_date', 'display_total_cost')
    fields = ('uniform', 'quantity', 'payment_option', 'loaned', 'transaction_date', 'display_total_cost')


class MultiItemTransactionInline(admin.TabularInline):
    model = MultiItemTransaction
    extra = 0
    show_change_link = True

    def display_total_cost(self, obj):
        return obj.total_cost()
    display_total_cost.short_description = "Total Cost"

    readonly_fields = ('transaction_date', 'display_total_cost')
    fields = ('payment_option', 'loaned', 'transaction_date', 'display_total_cost')


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'first_name', 'last_name', 'email', 'phone')
    search_fields = ('employee_id', 'first_name', 'last_name', 'email', 'phone')
    list_filter = ('email',)

@admin.register(Uniform)
class UniformAdmin(admin.ModelAdmin):
    list_display = ('name', 'size', 'price', 'stock_quantity', 'damaged_quantity')
    search_fields = ('name', 'size')
    list_filter = ('size',)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'employee', 'uniform', 'quantity', 'transaction_date', 'payment_option', 'loaned', 'returned')
    search_fields = ('employee__first_name', 'employee__last_name', 'uniform__name')
    list_filter = ('transaction_date', 'loaned', 'returned')

@admin.register(ReturnRecord)
class ReturnRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction', 'returned_quantity', 'return_date', 'damaged_quantity', 'damage_type')
    search_fields = ('transaction__employee__first_name', 'transaction__employee__last_name', 'transaction__uniform__name')
    list_filter = ('return_date', 'damage_type')
    readonly_fields = ('transaction',)

@admin.register(TransactionItem)
class TransactionItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction', 'uniform', 'quantity')
    search_fields = ('transaction__employee__first_name', 'transaction__employee__last_name', 'uniform__name')
    list_filter = ('transaction__transaction_date',)

@admin.register(ItemReturnRecord)
class ItemReturnRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_item', 'returned_quantity', 'return_date', 'damaged_quantity', 'damage_type')
    search_fields = ('transaction_item__transaction__employee__first_name', 'transaction_item__transaction__employee__last_name')
    list_filter = ('return_date', 'damage_type')
    readonly_fields = ('transaction_item',)

@admin.register(MultiItemTransaction)
class MultiItemTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'pk',
        'employee',
        'transaction_date',
        'payment_option',
        'loaned',
        'fully_returned',
    )
    list_filter = ('payment_option', 'loaned', 'returned')
    inlines = [TransactionItemInline]
    
    def fully_returned(self, obj):
        if obj.is_fully_returned:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    fully_returned.short_description = "Fully Returned"

@admin.register(SiteLocation)
class SiteLocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'address', 'description')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active',)
    ordering = ('name',)
    fieldsets = (
        (None, {
            'fields': ('name', 'address', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


    
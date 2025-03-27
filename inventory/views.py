from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, TemplateView, FormView, View
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Employee, Uniform, Transaction, ReturnRecord, TransactionItem, MultiItemTransaction, ItemReturnRecord, UniformType, UniformSize, SiteLocation, EquipmentItem
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
import io
from xhtml2pdf import pisa
from django.utils import timezone
from django.db.models import Sum, Count, Q, F
from .forms import ReturnTransactionForm, MultiItemTransactionForm, TransactionItemFormSet, SearchForm, CustomUserCreationForm, UserRoleForm, ImportFileForm, UniformWithSizesForm, UniformSizeForm, SiteLocationForm, EquipmentItemForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.generic.edit import FormView, UpdateView
import datetime
from django.contrib.auth.models import User
import pandas as pd
from django.db import transaction, IntegrityError
import os
from django.conf import settings
import base64
from django.views.decorators.http import require_GET
import json
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.views import LogoutView
from django.utils.http import url_has_allowed_host_and_scheme

# --- Custom Logout View ---
class CustomLogoutView(LogoutView):
    """
    Enhanced logout view that ensures browsers don't cache authenticated pages.
    """
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        
        # Add cache control headers to prevent caching
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        return response

# --- Search View ---
class SearchView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'inventory/search_results.html'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('query', '')
        search_type = self.request.GET.get('search_type', 'all')
        
        if query:
            # Initialize empty querysets
            employees = Employee.objects.none()
            uniforms = Uniform.objects.none()
            transactions = MultiItemTransaction.objects.none()
            locations = SiteLocation.objects.none()
            equipment = EquipmentItem.objects.none()
            
            # Filter based on search type
            if search_type in ['all', 'employees']:
                employees = Employee.objects.filter(
                    Q(first_name__icontains=query) | 
                    Q(last_name__icontains=query) | 
                    Q(employee_id__icontains=query) |
                    Q(email__icontains=query)
                )
            
            if search_type in ['all', 'uniforms']:
                uniforms = Uniform.objects.filter(
                    Q(name__icontains=query) | 
                    Q(size__icontains=query)
                )
            
            if search_type in ['all', 'transactions']:
                transactions = MultiItemTransaction.objects.filter(
                    Q(employee__first_name__icontains=query) |
                    Q(employee__last_name__icontains=query) |
                    Q(employee__employee_id__icontains=query) |
                    Q(items__uniform__name__icontains=query) |
                    Q(items__serial_number__icontains=query)
                ).distinct()
                
            if search_type in ['all', 'locations']:
                locations = SiteLocation.objects.filter(
                    Q(name__icontains=query) |
                    Q(address__icontains=query) |
                    Q(description__icontains=query)
                )
                
            if search_type in ['all', 'equipment']:
                equipment = EquipmentItem.objects.filter(
                    Q(name__icontains=query) |
                    Q(category__icontains=query) |
                    Q(serial_number__icontains=query) |
                    Q(asset_tag__icontains=query) |
                    Q(description__icontains=query) |
                    Q(notes__icontains=query) |
                    Q(location__name__icontains=query)
                )
            
            context['query'] = query
            context['search_type'] = search_type
            context['employees'] = employees
            context['uniforms'] = uniforms
            context['transactions'] = transactions
            context['locations'] = locations
            context['equipment'] = equipment
            context['has_results'] = (
                employees.exists() or 
                uniforms.exists() or 
                transactions.exists() or
                locations.exists() or
                equipment.exists()
            )
        
        context['form'] = SearchForm(initial={
            'query': query, 
            'search_type': search_type
        })
        
        return context

# --- Dashboard View ---
class DashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'inventory/dashboard.html'
    
    def test_func(self):
        return self.request.user.is_authenticated
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get current date
        today = timezone.now()
        thirty_days_ago = today - datetime.timedelta(days=30)
        
        # Total counts
        context['total_employees'] = Employee.objects.count()
        # Count unique uniform types instead of individual size variations
        context['total_uniforms'] = UniformType.objects.count()
        # Count total site locations
        context['total_locations'] = SiteLocation.objects.count()
        
        # Stock level counts (for the stock status overview)
        context['critical_stock_count'] = Uniform.objects.filter(stock_quantity__lt=5).count()
        context['low_stock_count'] = Uniform.objects.filter(stock_quantity__lt=10, stock_quantity__gte=5).count()
        context['warning_stock_count'] = Uniform.objects.filter(stock_quantity__lt=25, stock_quantity__gte=10).count()
        context['healthy_stock_count'] = Uniform.objects.filter(stock_quantity__gte=25).count()
        
        # Low stock uniforms (less than 25 items)
        context['low_stock_uniforms'] = Uniform.objects.filter(stock_quantity__lt=25).order_by('stock_quantity')
        
        # Recent transactions (last 30 days)
        context['recent_transactions'] = MultiItemTransaction.objects.filter(
            transaction_date__gte=thirty_days_ago
        ).order_by('-transaction_date')[:10]
        
        # Outstanding loans
        context['outstanding_loans'] = MultiItemTransaction.objects.filter(
            loaned=True, returned=False
        ).order_by('-transaction_date')[:10]
        
        # Transaction statistics
        context['transactions_this_month'] = MultiItemTransaction.objects.filter(
            transaction_date__gte=thirty_days_ago
        ).count()
        
        # Most active employees (most transactions in last 30 days)
        context['most_active_employees'] = Employee.objects.annotate(
            transaction_count=Count('multiitemtransaction', 
                                    filter=Q(multiitemtransaction__transaction_date__gte=thirty_days_ago))
        ).filter(transaction_count__gt=0).order_by('-transaction_count')[:5]
        
        # Financial calculations
        # 1. Total value of inventory in stock
        inventory_value = Uniform.objects.annotate(
            item_value=F('stock_quantity') * F('price')
        ).aggregate(total_value=Sum('item_value'))
        context['inventory_value'] = inventory_value['total_value'] or 0
        
        # 2. Total value of items distributed to employees
        # First, get all transaction items that haven't been returned
        distributed_value = TransactionItem.objects.annotate(
            remaining_quantity=F('quantity') - Sum(
                F('itemreturnrecord__returned_quantity'), 
                filter=Q(itemreturnrecord__isnull=False),
                default=0
            ),
            item_value=F('remaining_quantity') * F('uniform__price')
        ).aggregate(total_value=Sum('item_value'))
        context['distributed_value'] = distributed_value['total_value'] or 0
        
        # 3. Calculate total value of damaged items
        # Sum the value of damaged items from the uniform's damaged_quantity field
        damaged_uniform_value = Uniform.objects.annotate(
            damaged_value=F('damaged_quantity') * F('price')
        ).aggregate(total_damaged_value=Sum('damaged_value'))
        context['damaged_value'] = damaged_uniform_value['total_damaged_value'] or 0
        
        # Equipment financial data for the Financial Equipment Overview card
        # 1. Total equipment value
        equipment_total = EquipmentItem.objects.filter(
            purchase_price__isnull=False
        ).aggregate(total_value=Sum('purchase_price'))
        context['equipment_total_value'] = equipment_total['total_value'] or 0
        
        # 2. Assigned equipment value (replacing average equipment value)
        equipment_assigned = EquipmentItem.objects.filter(
            location__isnull=False,
            purchase_price__isnull=False
        ).aggregate(total_value=Sum('purchase_price'))
        context['equipment_assigned_value'] = equipment_assigned['total_value'] or 0
        
        # 3. Maintenance/repair value
        equipment_maintenance = EquipmentItem.objects.filter(
            status__in=['maintenance', 'repair'],
            purchase_price__isnull=False
        ).aggregate(total_value=Sum('purchase_price'))
        context['equipment_maintenance_value'] = equipment_maintenance['total_value'] or 0
        
        # 4. Unassigned equipment value
        equipment_unassigned = EquipmentItem.objects.filter(
            location__isnull=True,
            purchase_price__isnull=False
        ).aggregate(total_value=Sum('purchase_price'))
        context['equipment_unassigned_value'] = equipment_unassigned['total_value'] or 0
        
        return context

# --- Loading Page View ---
class LoadingPageView(TemplateView):
    template_name = 'inventory/loading_page.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any context data needed for the loading page
        return context
        
    def get(self, request, *args, **kwargs):
        # Check if user is authenticated for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            redirect_url = reverse_lazy('inventory:dashboard') if request.user.is_authenticated else reverse_lazy('inventory:login')
            return JsonResponse({'redirect': str(redirect_url)})
        return super().get(request, *args, **kwargs)

# --- Employee Views ---

class EmployeeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Employee
    template_name = 'inventory/employee_list.html'
    context_object_name = 'employees'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_queryset(self):
        # Check if we should show archived employees
        show_archived = self.request.GET.get('show_archived', 'false').lower() == 'true'
        
        # Filter employees based on archive status
        if show_archived:
            return Employee.objects.filter(is_archived=True)
        else:
            return Employee.objects.filter(is_archived=False)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass the current filter status to the template
        show_archived = self.request.GET.get('show_archived', 'false').lower() == 'true'
        context['show_archived'] = show_archived
        return context

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def toggle_employee_archive(request, pk):
    """Archive or unarchive an employee."""
    employee = get_object_or_404(Employee, pk=pk)
    
    if request.method == 'POST':
        # Toggle archive status
        if employee.is_archived:
            # Unarchive
            employee.is_archived = False
            employee.archive_date = None
            messages.success(request, f"{employee.first_name} {employee.last_name} has been restored to active status.")
        else:
            # Archive
            employee.is_archived = True
            employee.archive_date = timezone.now()
            messages.success(request, f"{employee.first_name} {employee.last_name} has been archived.")
        
        employee.save()
        
        # Redirect to referer or employee list
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('inventory:employee_list')
        
    # If not POST, show confirmation page
    return render(request, 'inventory/employee_archive_confirm.html', {
        'employee': employee
    })

class EmployeeDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Employee
    template_name = 'inventory/employee_detail.html'
    context_object_name = 'employee'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Only include multi-item transactions, renaming to just 'transactions'
        context['transactions'] = self.object.multiitemtransaction_set.all()
        return context


# --- Uniform Inventory View ---

class UniformListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Uniform
    template_name = 'inventory/uniform_list.html'
    context_object_name = 'uniforms'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def get(self, request):
        # Use render directly to ensure we're using the right template
        uniforms = Uniform.objects.all()
        low_stock_uniforms = Uniform.objects.filter(stock_quantity__lt=25)
        return render(request, 'inventory/uniform_list.html', {
            'uniforms': uniforms,
            'low_stock_uniforms': low_stock_uniforms
        })

# --- Transaction Views ---

class TransactionCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Transaction
    fields = ['employee', 'uniform', 'quantity', 'payment_option', 'loaned']
    template_name = 'inventory/transaction_form.html'
    success_url = reverse_lazy('inventory:employee_list')
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

class MultiItemTransactionCreateView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = MultiItemTransactionForm
    template_name = 'inventory/multi_transaction_form.html'
    success_url = reverse_lazy('inventory:employee_list')
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_success_url(self):
        # If an employee_id was provided, redirect back to that employee's detail page
        employee_id = self.request.GET.get('employee_id')
        if employee_id:
            return reverse_lazy('inventory:employee_detail', kwargs={'pk': employee_id})
        return self.success_url
    
    def get_initial(self):
        initial = super().get_initial()
        # Pre-select employee if employee_id is provided in the URL
        employee_id = self.request.GET.get('employee_id')
        if employee_id:
            try:
                # Make sure the employee exists
                employee = Employee.objects.get(pk=employee_id)
                initial['employee'] = employee.pk
            except Employee.DoesNotExist:
                pass
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['item_formset'] = TransactionItemFormSet(self.request.POST)
        else:
            context['item_formset'] = TransactionItemFormSet()
            
        # If we came from an employee profile, get the employee name to display in the page
        employee_id = self.request.GET.get('employee_id')
        if employee_id:
            try:
                employee = Employee.objects.get(pk=employee_id)
                context['selected_employee'] = employee
            except Employee.DoesNotExist:
                pass
                
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        item_formset = context['item_formset']
        
        if item_formset.is_valid():
            # Create the transaction instance but don't save to DB yet
            transaction = form.save(commit=False)
            transaction.save()
            
            # Process each form to ensure uniforms are correctly selected
            for item_form in item_formset:
                # Skip deleted forms
                if item_form.cleaned_data and not item_form.cleaned_data.get('DELETE', False):
                    uniform_id = item_form.cleaned_data.get('uniform')
                    
                    # Check if uniform_id is already a Uniform object
                    if uniform_id and not isinstance(uniform_id, Uniform):
                        try:
                            # Get the actual Uniform object
                            uniform = Uniform.objects.get(pk=uniform_id)
                            # Set the uniform instance on the form
                            item_form.instance.uniform = uniform
                        except Uniform.DoesNotExist:
                            # No matching uniform found - invalid form
                            item_form.add_error('uniform_type', 'No uniform found with this ID')
                            return self.form_invalid(form)
                    elif uniform_id and isinstance(uniform_id, Uniform):
                        # If it's already a Uniform object, use it directly
                        item_form.instance.uniform = uniform_id
                    # If no uniform ID provided directly, try to find by type and size
                    elif not item_form.instance.uniform:
                        # Get type and size from form
                        uniform_type = item_form.cleaned_data.get('uniform_type')
                        size = item_form.cleaned_data.get('size')
                        
                        if uniform_type and size:
                            try:
                                # Find the uniform by type and size
                                uniform = Uniform.objects.get(uniform_type=uniform_type, size=size)
                                # Set the uniform in the cleaned data
                                item_form.instance.uniform = uniform
                            except Uniform.DoesNotExist:
                                # No matching uniform found - invalid form
                                item_form.add_error('uniform_type', 'No uniform found for this type and size')
                                return self.form_invalid(form)
            
            # Now, save the formset
            item_formset.instance = transaction
            item_formset.save()
            
            # Check if this is a prior record - we'll still record it but not reduce inventory
            is_prior_record = form.cleaned_data.get('is_prior_record', False)
            
            # Update stock quantities for each uniform only if not a prior record
            for item_form in item_formset:
                if item_form.cleaned_data and not item_form.cleaned_data.get('DELETE', False):
                    uniform = item_form.instance.uniform  # Get the uniform from the saved instance
                    quantity = item_form.cleaned_data['quantity']
                    
                    # Only check inventory and reduce stock for new transactions, not prior records
                    if not is_prior_record:
                        # Check if there's enough stock
                        if uniform.stock_quantity < quantity:
                            messages.error(self.request, f'Not enough {uniform} in stock. Available: {uniform.stock_quantity}')
                            # Delete the transaction since we can't fulfill it
                            transaction.delete()
                            return self.form_invalid(form)
                        
                        # Reduce the stock quantity
                        uniform.stock_quantity -= quantity
                        uniform.save()
            
            # Create a more descriptive success message
            employee = transaction.employee
            employee_name = f"{employee.first_name} {employee.last_name}" if employee.first_name and employee.last_name else employee.employee_id
            
            if is_prior_record:
                messages.success(self.request, f'Prior record for {employee_name} created successfully. Inventory not affected.')
            else:
                messages.success(self.request, f'Transaction for {employee_name} created successfully.')
            
            return super().form_valid(form)
        else:
            return self.form_invalid(form)

# --- PDF Generation ---

def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html  = template.render(context_dict)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        return result.getvalue()
    return None

def employee_pdf(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    transactions = employee.multiitemtransaction_set.all().prefetch_related(
        'items', 'items__uniform', 'items__itemreturnrecord_set'
    ).order_by('-transaction_date')
    
    # Calculate summary statistics
    total_items = 0
    total_returned = 0
    total_value = 0
    outstanding_value = 0
    
    for transaction in transactions:
        for item in transaction.items.all():
            item_quantity = item.quantity
            total_items += item_quantity
            total_value += item_quantity * item.uniform.price
            
            if hasattr(item, 'total_returned'):
                returned = item.total_returned
            else:
                returned = item.itemreturnrecord_set.aggregate(
                    total=Sum('returned_quantity'))['total'] or 0
                
            total_returned += returned
            outstanding = item_quantity - returned
            outstanding_value += outstanding * item.uniform.price
    
    # Get the logo as base64
    logo_path = os.path.join(settings.BASE_DIR, 'inventory/static/inventory/images/Round_logo.png')
    with open(logo_path, 'rb') as img_file:
        logo_data = base64.b64encode(img_file.read()).decode('utf-8')
    
    context = {
        'employee': employee,
        'transactions': transactions,
        'now': timezone.now(),
        'total_items': total_items,
        'returned_items': total_returned,
        'outstanding_items': total_items - total_returned,
        'total_value': total_value,
        'outstanding_value': outstanding_value,
        'logo_data': logo_data
    }
    
    template = get_template('inventory/employee_pdf.html')
    html = template.render(context)
    
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f'Employee_{employee.employee_id}_{employee.last_name}_Uniforms.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse("Error generating PDF", status=400)

# --- Return Processing ---

@login_required
def process_return(request, pk):
    # Get the transaction
    transaction = get_object_or_404(Transaction, pk=pk)
    
    # Calculate how many items can still be returned
    returned_quantity = transaction.total_returned
    remaining = transaction.quantity - returned_quantity
    
    if request.method == 'POST':
        # Get form data
        all_returned = request.POST.get('all_returned')
        has_damaged_items = request.POST.get('has_damaged_items') == 'on'
        
        # Determine quantity to return
        if all_returned == 'yes':
            return_quantity = remaining
        else:
            try:
                return_quantity = int(request.POST.get('returned_quantity', 0))
                if return_quantity <= 0 or return_quantity > remaining:
                    messages.error(request, f"Invalid quantity. You can return between 1 and {remaining} items.")
                    return render(request, 'inventory/return.html', {
                        'transaction': transaction,
                        'returned_quantity': returned_quantity,
                        'remaining': remaining,
                    })
            except ValueError:
                messages.error(request, "Please enter a valid number.")
                return render(request, 'inventory/return.html', {
                    'transaction': transaction,
                    'returned_quantity': returned_quantity,
                    'remaining': remaining,
                })
        
        # Process damaged items if applicable
        damaged_quantity = 0
        damage_type = 'none'
        damage_notes = ''
        
        if has_damaged_items:
            try:
                damaged_quantity = int(request.POST.get('damaged_quantity', 0))
                if damaged_quantity < 0 or damaged_quantity > return_quantity:
                    messages.error(request, f"Invalid damaged quantity. It should be between 0 and {return_quantity}.")
                    return render(request, 'inventory/return.html', {
                        'transaction': transaction,
                        'returned_quantity': returned_quantity,
                        'remaining': remaining,
                    })
                
                damage_type = request.POST.get('damage_type', 'none')
                if damage_type not in [choice[0] for choice in ReturnRecord.DAMAGE_TYPE_CHOICES]:
                    damage_type = 'none'
                
                damage_notes = request.POST.get('damage_notes', '')
                
            except ValueError:
                messages.error(request, "Please enter a valid number for damaged items.")
                return render(request, 'inventory/return.html', {
                    'transaction': transaction,
                    'returned_quantity': returned_quantity,
                    'remaining': remaining,
                })
        
        # Create the return record
        ReturnRecord.objects.create(
            transaction=transaction,
            returned_quantity=return_quantity,
            damaged_quantity=damaged_quantity,
            damage_type=damage_type,
            damage_notes=damage_notes
        )
        
        # Update uniform stock
        usable_returned = return_quantity - damaged_quantity
        transaction.uniform.stock_quantity += usable_returned
        
        # Update damaged quantities
        if damaged_quantity > 0:
            transaction.uniform.damaged_quantity += damaged_quantity
        
        transaction.uniform.save()
        
        # Check if transaction is fully returned
        if transaction.total_returned == transaction.quantity:
            transaction.returned = True
            transaction.return_date = timezone.now()
            transaction.save()
            messages.success(request, f"All {transaction.quantity} items have been returned.")
        else:
            new_remaining = transaction.quantity - transaction.total_returned
            messages.success(request, f"{return_quantity} items returned. {new_remaining} items still outstanding.")
        
        if damaged_quantity > 0:
            messages.warning(request, f"{damaged_quantity} damaged items recorded.")
        
        return redirect('inventory:employee_detail', pk=transaction.employee.pk)
    
    return render(request, 'inventory/return.html', {
        'transaction': transaction,
        'returned_quantity': returned_quantity,
        'remaining': remaining,
    })

@login_required
def process_item_return(request, pk):
    # Get the transaction item
    transaction_item = get_object_or_404(TransactionItem, pk=pk)
    
    # Calculate how many items can still be returned
    returned_quantity = transaction_item.total_returned
    remaining = transaction_item.quantity - returned_quantity
    
    if request.method == 'POST':
        form = ReturnTransactionForm(request.POST)
        
        if form.is_valid():
            # Get cleaned form data
            all_returned = form.cleaned_data['all_returned']
            has_damaged_items = form.cleaned_data['has_damaged_items']
            
            # Determine quantity to return
            if all_returned == 'yes':
                return_quantity = remaining
            else:
                return_quantity = form.cleaned_data['returned_quantity']
                if not return_quantity or return_quantity <= 0 or return_quantity > remaining:
                    messages.error(request, f"Invalid quantity. You can return between 1 and {remaining} items.")
                    return render(request, 'inventory/item_return.html', {
                        'transaction_item': transaction_item,
                        'returned_quantity': returned_quantity,
                        'remaining': remaining,
                        'form': form,
                    })
            
            # Process damaged items if applicable
            damaged_quantity = 0
            damage_type = 'none'
            damage_notes = ''
            
            if has_damaged_items:
                damaged_quantity = form.cleaned_data['damaged_quantity'] or 0
                damage_type = form.cleaned_data['damage_type'] or 'none'
                damage_notes = form.cleaned_data['damage_notes'] or ''
            
            # Create the return record
            ItemReturnRecord.objects.create(
                transaction_item=transaction_item,
                returned_quantity=return_quantity,
                damaged_quantity=damaged_quantity,
                damage_type=damage_type,
                damage_notes=damage_notes
            )
            
            # Update uniform stock
            usable_returned = return_quantity - damaged_quantity
            transaction_item.uniform.stock_quantity += usable_returned
            
            # Update damaged quantities
            if damaged_quantity > 0:
                transaction_item.uniform.damaged_quantity += damaged_quantity
            
            transaction_item.uniform.save()
            
            # Check if transaction is fully returned
            transaction = transaction_item.transaction
            if transaction.is_fully_returned:
                transaction.returned = True
            transaction.return_date = timezone.now()
            transaction.save()
            
            if transaction.is_fully_returned:
                messages.success(request, "All items have been returned for this transaction.")
            else:
                new_remaining = transaction_item.quantity - transaction_item.total_returned
                messages.success(request, f"{return_quantity} items returned. {new_remaining} items still outstanding.")
            
            if damaged_quantity > 0:
                messages.warning(request, f"{damaged_quantity} damaged items recorded.")
            
            return redirect('inventory:employee_detail', pk=transaction.employee.pk)
    else:
        # For GET requests, initialize the form
        form = ReturnTransactionForm()
    
    return render(request, 'inventory/item_return.html', {
        'transaction_item': transaction_item,
        'returned_quantity': returned_quantity,
        'remaining': remaining,
        'form': form,
    })

# --- User Management Views ---

class UserListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = User
    template_name = 'inventory/user_list.html'
    context_object_name = 'users'
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def get_queryset(self):
        return User.objects.all().order_by('username')

class UserCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = 'inventory/user_form.html'
    success_url = reverse_lazy('inventory:user_list')
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['role_form'] = UserRoleForm(self.request.POST)
        else:
            context['role_form'] = UserRoleForm()
        return context
    
    def form_valid(self, form):
        role_form = UserRoleForm(self.request.POST)
        if role_form.is_valid():
            user = form.save()
            role_form.save(user)
            messages.success(self.request, f'User {user.username} was created successfully.')
            return redirect(self.success_url)
        else:
            return self.form_invalid(form)

@login_required
def user_edit_role(request, pk):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to edit user roles.')
        return redirect('inventory:dashboard')
    
    user = get_object_or_404(User, pk=pk)
    
    # Determine initial role
    initial_role = 'viewer'
    if user.is_superuser:
        initial_role = 'admin'
    elif user.is_staff:
        initial_role = 'staff'
    
    if request.method == 'POST':
        form = UserRoleForm(request.POST)
        if form.is_valid():
            form.save(user)
            messages.success(request, f'Role for {user.username} updated successfully.')
            return redirect('user_list')
    else:
        form = UserRoleForm(initial={'role': initial_role})
    
    return render(request, 'inventory/user_role_form.html', {
        'form': form,
        'user': user
    })

@login_required
def damaged_items_report(request):
    """View to display statistics about damaged items"""
    
    # Get all return records with damaged items
    return_records = ReturnRecord.objects.filter(damaged_quantity__gt=0)
    item_return_records = ItemReturnRecord.objects.filter(damaged_quantity__gt=0)
    
    # Calculate statistics
    total_damaged = sum(record.damaged_quantity for record in return_records) + sum(record.damaged_quantity for record in item_return_records)
    
    # Group by damage type
    damage_type_stats = {}
    for damage_type, damage_label in ReturnRecord.DAMAGE_TYPE_CHOICES:
        damage_count = sum(record.damaged_quantity for record in return_records.filter(damage_type=damage_type))
        damage_count += sum(record.damaged_quantity for record in item_return_records.filter(damage_type=damage_type))
        if damage_count > 0:
            damage_type_stats[damage_label] = damage_count
    
    # Group by uniform
    uniform_damaged = {}
    for record in return_records:
        uniform = record.transaction.uniform
        if uniform in uniform_damaged:
            uniform_damaged[uniform] += record.damaged_quantity
        else:
            uniform_damaged[uniform] = record.damaged_quantity
    
    for record in item_return_records:
        uniform = record.transaction_item.uniform
        if uniform in uniform_damaged:
            uniform_damaged[uniform] += record.damaged_quantity
        else:
            uniform_damaged[uniform] = record.damaged_quantity
    
    # Calculate total value of damaged items
    total_value = sum(uniform.price * qty for uniform, qty in uniform_damaged.items())
    
    # Get recent damaged returns for the summary section
    recent_damages = list(return_records.order_by('-return_date')[:5]) + list(item_return_records.order_by('-return_date')[:5])
    recent_damages.sort(key=lambda x: x.return_date, reverse=True)
    recent_damages = recent_damages[:5]  # Get top 5
    
    # Get all damaged records for the detailed listing
    all_return_records = list(return_records.order_by('-return_date'))
    all_item_return_records = list(item_return_records.order_by('-return_date'))
    
    # Combine all records with damaged items
    all_damaged_records = []
    
    # Process ReturnRecord objects
    for record in all_return_records:
        if record.damaged_quantity > 0:
            all_damaged_records.append({
                'date': record.return_date,
                'employee': record.transaction.employee,
                'uniform': record.transaction.uniform,
                'damage_type': record.get_damage_type_display(),
                'damaged_quantity': record.damaged_quantity,
                'damage_notes': record.damage_notes,
                'transaction_id': record.transaction.id,
                'record_type': 'ReturnRecord'
            })
    
    # Process ItemReturnRecord objects
    for record in all_item_return_records:
        if record.damaged_quantity > 0:
            all_damaged_records.append({
                'date': record.return_date,
                'employee': record.transaction_item.transaction.employee,
                'uniform': record.transaction_item.uniform,
                'damage_type': record.get_damage_type_display(),
                'damaged_quantity': record.damaged_quantity,
                'damage_notes': record.damage_notes,
                'transaction_id': record.transaction_item.transaction.id,
                'record_type': 'ItemReturnRecord'
            })
    
    # Sort combined records by date (newest first)
    all_damaged_records.sort(key=lambda x: x['date'], reverse=True)
    
    context = {
        'total_damaged': total_damaged,
        'damage_type_stats': damage_type_stats,
        'uniform_damaged': uniform_damaged,
        'total_value': total_value,
        'recent_damages': recent_damages,
        'all_damaged_records': all_damaged_records,
    }
    
    return render(request, 'inventory/damaged_items_report.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def import_employees(request):
    """View to handle importing employees from Excel file."""
    if request.method == 'POST':
        form = ImportFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Process the Excel file
                excel_file = request.FILES['file']
                df = pd.read_excel(excel_file)
                
                # Validate required columns
                required_columns = ['employee_id', 'first_name', 'last_name']
                for column in required_columns:
                    if column not in df.columns:
                        messages.error(request, f"Missing required column: {column}")
                        return redirect('inventory:import_employees')
                
                # Track results
                success_count = 0
                error_count = 0
                errors = []
                
                # Process each row in the dataframe
                with transaction.atomic():
                    for index, row in df.iterrows():
                        try:
                            # Extract data from the row
                            employee_data = {
                                'employee_id': str(row['employee_id']).strip(),
                                'first_name': str(row['first_name']).strip(),
                                'last_name': str(row['last_name']).strip(),
                                'email': str(row.get('email', '')).strip() if pd.notna(row.get('email', '')) else None,
                                'phone': str(row.get('phone', '')).strip() if pd.notna(row.get('phone', '')) else None
                            }
                            
                            # Skip blank rows
                            if not employee_data['employee_id'] or not employee_data['first_name'] or not employee_data['last_name']:
                                continue
                            
                            # Check if employee already exists
                            employee, created = Employee.objects.update_or_create(
                                employee_id=employee_data['employee_id'],
                                defaults={
                                    'first_name': employee_data['first_name'],
                                    'last_name': employee_data['last_name'],
                                    'email': employee_data['email'],
                                    'phone': employee_data['phone']
                                }
                            )
                            
                            if created:
                                success_count += 1
                            else:
                                # Updated existing employee
                                success_count += 1
                                
                        except Exception as e:
                            error_count += 1
                            errors.append(f"Row {index+2}: {str(e)}")
                
                # Report results
                if success_count > 0:
                    messages.success(request, f"Successfully imported {success_count} employees.")
                if error_count > 0:
                    messages.warning(request, f"Encountered {error_count} errors during import.")
                    for error in errors[:10]:  # Show first 10 errors
                        messages.error(request, error)
                    if len(errors) > 10:
                        messages.error(request, f"... and {len(errors) - 10} more errors.")
                
                return redirect('inventory:employee_list')
            
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
    else:
        form = ImportFileForm()
    
    return render(request, 'inventory/import_employees.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def export_employee_template(request):
    """Generate a template Excel file for employee imports."""
    # Create a DataFrame with the column headers
    df = pd.DataFrame(columns=['employee_id', 'first_name', 'last_name', 'email', 'phone'])
    
    # Add sample data
    sample_data = [
        {'employee_id': 'EMP001', 'first_name': 'John', 'last_name': 'Doe', 'email': 'john.doe@example.com', 'phone': '555-123-4567'},
        {'employee_id': 'EMP002', 'first_name': 'Jane', 'last_name': 'Smith', 'email': 'jane.smith@example.com', 'phone': '555-987-6543'}
    ]
    df = pd.concat([df, pd.DataFrame(sample_data)], ignore_index=True)
    
    # Create a response with the Excel file
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=employee_import_template.xlsx'
    
    # Write the DataFrame to the response
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Employees')
    
    return response

# --- Asset Breakdown View ---
class AssetBreakdownView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'inventory/asset_breakdown.html'
    
    def test_func(self):
        return self.request.user.is_authenticated
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get uniform categories and sizes for grouping
        uniforms = Uniform.objects.all()
        categories = list(set([u.name for u in uniforms]))
        sizes = list(set([u.size for u in uniforms]))
        
        # Calculate inventory value (items in stock) by category and size
        inventory_by_category = {}
        for category in categories:
            category_uniforms = Uniform.objects.filter(name=category)
            category_value = category_uniforms.annotate(
                item_value=F('stock_quantity') * F('price')
            ).aggregate(total_value=Sum('item_value'))['total_value'] or 0
            inventory_by_category[category] = category_value
        
        inventory_by_size = {}
        for size in sizes:
            size_uniforms = Uniform.objects.filter(size=size)
            size_value = size_uniforms.annotate(
                item_value=F('stock_quantity') * F('price')
            ).aggregate(total_value=Sum('item_value'))['total_value'] or 0
            inventory_by_size[size] = size_value
        
        # Calculate distributed value (items with employees) by category and size
        distributed_by_category = {}
        for category in categories:
            category_items = TransactionItem.objects.filter(uniform__name=category).annotate(
                remaining_quantity=F('quantity') - Sum(
                    F('itemreturnrecord__returned_quantity'), 
                    filter=Q(itemreturnrecord__isnull=False),
                    default=0
                ),
                item_value=F('remaining_quantity') * F('uniform__price')
            ).aggregate(total_value=Sum('item_value'))['total_value'] or 0
            distributed_by_category[category] = category_items
        
        distributed_by_size = {}
        for size in sizes:
            size_items = TransactionItem.objects.filter(uniform__size=size).annotate(
                remaining_quantity=F('quantity') - Sum(
                    F('itemreturnrecord__returned_quantity'), 
                    filter=Q(itemreturnrecord__isnull=False),
                    default=0
                ),
                item_value=F('remaining_quantity') * F('uniform__price')
            ).aggregate(total_value=Sum('item_value'))['total_value'] or 0
            distributed_by_size[size] = size_items
        
        # Top 10 most valuable items in inventory
        top_inventory_items = Uniform.objects.annotate(
            item_value=F('stock_quantity') * F('price')
        ).order_by('-item_value')[:10]
        
        # Top 10 most valuable items distributed to employees
        top_distributed_uniforms = {}
        for uniform in Uniform.objects.all():
            uniform_value = TransactionItem.objects.filter(uniform=uniform).annotate(
                remaining_quantity=F('quantity') - Sum(
                    F('itemreturnrecord__returned_quantity'), 
                    filter=Q(itemreturnrecord__isnull=False),
                    default=0
                ),
                item_value=F('remaining_quantity') * F('uniform__price')
            ).aggregate(total_value=Sum('item_value'))['total_value'] or 0
            if uniform_value > 0:
                top_distributed_uniforms[uniform] = uniform_value
        
        # Sort the dictionary and get top 10
        top_distributed_items = sorted(top_distributed_uniforms.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Total values (same as dashboard)
        inventory_value = Uniform.objects.annotate(
            item_value=F('stock_quantity') * F('price')
        ).aggregate(total_value=Sum('item_value'))['total_value'] or 0
        
        distributed_value = TransactionItem.objects.annotate(
            remaining_quantity=F('quantity') - Sum(
                F('itemreturnrecord__returned_quantity'), 
                filter=Q(itemreturnrecord__isnull=False),
                default=0
            ),
            item_value=F('remaining_quantity') * F('uniform__price')
        ).aggregate(total_value=Sum('item_value'))['total_value'] or 0
        
        # Calculate damaged items value
        damaged_value = Uniform.objects.annotate(
            damaged_value=F('damaged_quantity') * F('price')
        ).aggregate(total_damaged_value=Sum('damaged_value'))['total_damaged_value'] or 0
        
        # Damaged items by type
        damage_types = dict(ItemReturnRecord.DAMAGE_TYPE_CHOICES)
        damaged_by_type = {}
        
        for damage_code, damage_name in damage_types.items():
            type_value = ItemReturnRecord.objects.filter(
                damage_type=damage_code, 
                damaged_quantity__gt=0
            ).annotate(
                item_value=F('damaged_quantity') * F('transaction_item__uniform__price')
            ).aggregate(total_value=Sum('item_value'))['total_value'] or 0
            
            if type_value > 0:
                damaged_by_type[damage_name] = type_value
        
        context.update({
            'inventory_value': inventory_value,
            'distributed_value': distributed_value,
            'damaged_value': damaged_value,
            'total_asset_value': inventory_value + distributed_value,
            'inventory_by_category': sorted(inventory_by_category.items(), key=lambda x: x[1], reverse=True),
            'inventory_by_size': sorted(inventory_by_size.items(), key=lambda x: x[1], reverse=True),
            'distributed_by_category': sorted(distributed_by_category.items(), key=lambda x: x[1], reverse=True),
            'distributed_by_size': sorted(distributed_by_size.items(), key=lambda x: x[1], reverse=True),
            'top_inventory_items': top_inventory_items,
            'top_distributed_items': top_distributed_items,
            'damaged_by_type': sorted(damaged_by_type.items(), key=lambda x: x[1], reverse=True),
        })
        
        return context

# --- Uniform Add View ---
class UniformWithSizesCreateView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'inventory/uniform_with_sizes_form.html'
    form_class = UniformWithSizesForm
    success_url = reverse_lazy('inventory:uniform_list')
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def form_valid(self, form):
        # Get or create the uniform type
        uniform_type = None
        if form.cleaned_data.get('uniform_type'):
            uniform_type = form.cleaned_data['uniform_type']
        elif form.cleaned_data.get('new_uniform_type'):
            # Create a new uniform type
            try:
                # Check if a uniform type with this name already exists
                uniform_type = UniformType.objects.get(name=form.cleaned_data['new_uniform_type'])
                messages.info(
                    self.request,
                    f'Using existing uniform type "{uniform_type.name}"'
                )
            except UniformType.DoesNotExist:
                uniform_type = UniformType.objects.create(
                    name=form.cleaned_data['new_uniform_type'],
                    description=form.cleaned_data.get('description', '')
                )
                messages.success(
                    self.request,
                    f'Created new uniform type "{uniform_type.name}"'
                )
        
        price = form.cleaned_value
        sizes = UniformSize.objects.all()
        
        # Create a uniform for each size with quantity > 0
        uniforms_created = 0
        for size in sizes:
            quantity = form.cleaned_data.get(f'quantity_{size.id}', 0)
            if quantity > 0:
                # Check if this uniform already exists
                try:
                    uniform = Uniform.objects.get(name=uniform_type.name, size=size.name)
                    # Update existing uniform
                    uniform.price = price
                    uniform.stock_quantity += quantity
                    uniform.uniform_type = uniform_type
                    uniform.save()
                    messages.success(
                        self.request, 
                        f'Updated existing {uniform.name} - {uniform.size} (added {quantity} to stock)'
                    )
                except Uniform.DoesNotExist:
                    # Create new uniform
                    uniform = Uniform.objects.create(
                        name=uniform_type.name,
                        size=size.name,
                        price=price,
                        stock_quantity=quantity,
                        uniform_type=uniform_type
                    )
                    messages.success(
                        self.request, 
                        f'Created new {uniform.name} - {uniform.size} with {quantity} in stock'
                    )
                uniforms_created += 1
        
        if uniforms_created > 0:
            messages.success(
                self.request, 
                f'Successfully added/updated {uniforms_created} uniform items with different sizes'
            )
        else:
            messages.warning(self.request, 'No uniforms were created or updated. Please specify quantities.')
            return self.form_invalid(form)
            
        return super().form_valid(form)

# --- Uniform Size Management View ---
class UniformSizeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = UniformSize
    template_name = 'inventory/uniform_size_list.html'
    context_object_name = 'sizes'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = UniformSizeForm()
        return context

class UniformSizeCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = UniformSize
    form_class = UniformSizeForm
    template_name = 'inventory/uniform_size_form.html'
    success_url = reverse_lazy('inventory:uniform_sizes')
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def form_valid(self, form):
        messages.success(self.request, f'Size "{form.instance.name}" created successfully')
        return super().form_valid(form)

@method_decorator(csrf_exempt, name='dispatch')
class UniformSizeUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def post(self, request, pk):
        try:
            size = UniformSize.objects.get(pk=pk)
            data = json.loads(request.body)
            
            # Validate the data
            if not data.get('name'):
                return JsonResponse({'error': 'Size name is required'}, status=400)
            
            if not data.get('display_order'):
                return JsonResponse({'error': 'Display order is required'}, status=400)
            
            try:
                display_order = int(data['display_order'])
            except ValueError:
                return JsonResponse({'error': 'Display order must be a number'}, status=400)
            
            # Update the size
            size.name = data['name']
            size.display_order = display_order
            size.save()
            
            return JsonResponse({
                'name': size.name,
                'display_order': size.display_order
            })
            
        except UniformSize.DoesNotExist:
            return JsonResponse({'error': 'Size not found'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

@require_GET
def uniform_stock_api(request, uniform_id):
    """
    API endpoint to get stock quantity for a uniform.
    """
    uniform = get_object_or_404(Uniform, id=uniform_id)
    return JsonResponse({
        'stock_quantity': uniform.stock_quantity,
        'id': uniform.id,
        'name': str(uniform)
    })

@require_GET
def uniform_type_sizes_api(request, type_id):
    """
    API endpoint to get all sizes available for a uniform type.
    """
    uniform_type = get_object_or_404(UniformType, id=type_id)
    
    # Get all sizes that are available for this uniform type
    sizes = []
    uniforms = Uniform.objects.filter(uniform_type=uniform_type)
    for uniform in uniforms:
        if uniform.size and uniform.size not in [s['name'] for s in sizes]:
            sizes.append({
                'id': uniform.size,  # Use the size string as the ID
                'name': uniform.size
            })
    
    return JsonResponse({
        'type_id': uniform_type.id,
        'type_name': uniform_type.name,
        'sizes': sizes
    })

@require_GET
def uniform_by_type_size_api(request):
    """
    API endpoint to get a uniform by type and size.
    """
    type_id = request.GET.get('type_id')
    size = request.GET.get('size_id')  # This is actually the size string, not an ID
    
    if not type_id or not size:
        return JsonResponse({'error': 'Both type_id and size_id are required'}, status=400)
    
    try:
        uniform_type = UniformType.objects.get(id=type_id)
        
        try:
            uniform = Uniform.objects.get(uniform_type=uniform_type, size=size)
            return JsonResponse({
                'uniform': {
                    'id': uniform.id,
                    'name': str(uniform),
                    'stock_quantity': uniform.stock_quantity,
                    'price': str(uniform.price)
                }
            })
        except Uniform.DoesNotExist:
            return JsonResponse({'error': 'No uniform found with this type and size'}, status=404)
            
    except UniformType.DoesNotExist:
        return JsonResponse({'error': 'Invalid type ID'}, status=404)

# --- Site Location Views ---
class SiteLocationListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View to list all site locations."""
    model = SiteLocation
    template_name = 'inventory/site_location_list.html'
    context_object_name = 'locations'
    
    def test_func(self):
        return self.request.user.is_authenticated
    
    def get_queryset(self):
        # Default ordering by name, but you can change it based on GET parameters
        order_by = self.request.GET.get('order_by', 'name')
        # Filter active/inactive based on GET parameters
        show_inactive = self.request.GET.get('show_inactive', False)
        
        queryset = SiteLocation.objects.all()
        if not show_inactive:
            queryset = queryset.filter(is_active=True)
            
        # Add ordering
        if order_by == 'name':
            queryset = queryset.order_by('name')
        elif order_by == 'created':
            queryset = queryset.order_by('-created_at')
        elif order_by == 'updated':
            queryset = queryset.order_by('-updated_at')
        
        # Annotate each location with the count of equipment items and total value
        queryset = queryset.annotate(
            equipment_count=Count('equipment_items'),
            equipment_value=Sum(
                F('equipment_items__purchase_price'),
                filter=Q(equipment_items__purchase_price__isnull=False)
            )
        )
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add filter parameters to context for the template
        context['show_inactive'] = self.request.GET.get('show_inactive', False)
        context['order_by'] = self.request.GET.get('order_by', 'name')
        
        # Display count of inactive locations if only showing active
        if not context['show_inactive']:
            context['inactive_count'] = SiteLocation.objects.filter(is_active=False).count()
            
        return context


class SiteLocationCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View to create a new site location."""
    model = SiteLocation
    form_class = SiteLocationForm
    template_name = 'inventory/site_location_form.html'
    success_url = reverse_lazy('inventory:site_location_list')
    
    def test_func(self):
        # Require staff privileges to create locations
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def form_valid(self, form):
        messages.success(self.request, f"Location '{form.instance.name}' was created successfully.")
        return super().form_valid(form)


class SiteLocationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View to display site location details."""
    model = SiteLocation
    template_name = 'inventory/site_location_detail.html'
    context_object_name = 'location'
    
    def test_func(self):
        return self.request.user.is_authenticated
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        location = self.get_object()
        
        # Get equipment items assigned to this location
        context['equipment_items'] = EquipmentItem.objects.filter(location=location).order_by('name')
        context['equipment_count'] = context['equipment_items'].count()
        
        return context


class SiteLocationUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View to update an existing site location."""
    model = SiteLocation
    form_class = SiteLocationForm
    template_name = 'inventory/site_location_form.html'
    
    def test_func(self):
        # Require staff privileges to update locations
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_success_url(self):
        return reverse_lazy('inventory:site_location_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f"Location '{form.instance.name}' was updated successfully.")
        return super().form_valid(form)


@login_required
def toggle_site_location_status(request, pk):
    """View to toggle a location's active status."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('inventory:site_location_list')
    
    location = get_object_or_404(SiteLocation, pk=pk)
    location.is_active = not location.is_active
    location.save()
    
    status = "activated" if location.is_active else "deactivated"
    messages.success(request, f"Location '{location.name}' has been {status}.")
    
    # Redirect back to either the list or detail page based on where the request came from
    referring_page = request.META.get('HTTP_REFERER', None)
    if referring_page and 'detail' in referring_page:
        return redirect('inventory:site_location_detail', pk=location.pk)
    else:
        return redirect('inventory:site_location_list')

# --- Equipment Item Views ---
class EquipmentItemListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View to list all equipment items."""
    model = EquipmentItem
    template_name = 'inventory/equipment_item_list.html'
    context_object_name = 'equipment_items'
    
    def test_func(self):
        return self.request.user.is_authenticated
    
    def get_queryset(self):
        queryset = EquipmentItem.objects.all()
        
        # Filter by status if provided
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        # Filter by location if provided
        location_filter = self.request.GET.get('location')
        if location_filter:
            queryset = queryset.filter(location_id=location_filter)
            
        # Filter by category if provided
        category_filter = self.request.GET.get('category')
        if category_filter:
            queryset = queryset.filter(category=category_filter)
            
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(serial_number__icontains=search_query) |
                Q(asset_tag__icontains=search_query) |
                Q(category__icontains=search_query)
            )
            
        # Ordering
        order_by = self.request.GET.get('order_by', 'name')
        if order_by == 'name':
            queryset = queryset.order_by('name')
        elif order_by == 'category':
            queryset = queryset.order_by('category', 'name')
        elif order_by == 'status':
            queryset = queryset.order_by('status', 'name')
        elif order_by == 'location':
            queryset = queryset.order_by('location__name', 'name')
        elif order_by == 'purchase_date':
            queryset = queryset.order_by('-purchase_date')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter data for the template
        context['status_filter'] = self.request.GET.get('status', '')
        context['location_filter'] = self.request.GET.get('location', '')
        context['category_filter'] = self.request.GET.get('category', '')
        context['search_query'] = self.request.GET.get('search', '')
        context['order_by'] = self.request.GET.get('order_by', 'name')
        
        # Get unique categories and statuses for filter dropdowns
        context['categories'] = EquipmentItem.objects.values_list('category', flat=True).distinct().order_by('category')
        context['status_choices'] = EquipmentItem.STATUS_CHOICES
        context['locations'] = SiteLocation.objects.filter(is_active=True).order_by('name')
        
        return context


class EquipmentItemCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """View to create a new equipment item."""
    model = EquipmentItem
    form_class = EquipmentItemForm
    template_name = 'inventory/equipment_item_form.html'
    success_url = reverse_lazy('inventory:equipment_item_list')
    
    def test_func(self):
        # Require staff privileges to create equipment items
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def form_valid(self, form):
        messages.success(self.request, f"Equipment item '{form.instance.name}' was created successfully.")
        return super().form_valid(form)
        
    def get_initial(self):
        initial = super().get_initial()
        # Pre-fill location if provided in URL
        location_id = self.request.GET.get('location')
        if location_id:
            try:
                initial['location'] = SiteLocation.objects.get(id=location_id)
            except SiteLocation.DoesNotExist:
                pass
        return initial


class EquipmentItemDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View to display equipment item details."""
    model = EquipmentItem
    template_name = 'inventory/equipment_item_detail.html'
    context_object_name = 'equipment_item'
    
    def test_func(self):
        return self.request.user.is_authenticated
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add all active locations for the location dropdown
        context['locations'] = SiteLocation.objects.filter(is_active=True).order_by('name')
        return context


class EquipmentItemUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View to update an existing equipment item."""
    model = EquipmentItem
    form_class = EquipmentItemForm
    template_name = 'inventory/equipment_item_form.html'
    
    def test_func(self):
        # Require staff privileges to update equipment items
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_success_url(self):
        return reverse_lazy('inventory:equipment_item_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f"Equipment item '{form.instance.name}' was updated successfully.")
        return super().form_valid(form)


class EquipmentItemAssignView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View to assign equipment to a location."""
    model = EquipmentItem
    template_name = 'inventory/equipment_item_assign.html'
    fields = ['location']
    
    def test_func(self):
        # Require staff privileges to assign equipment
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Limit location choices to active locations
        form.fields['location'].queryset = SiteLocation.objects.filter(is_active=True)
        form.fields['location'].empty_label = "No location (unassigned)"
        form.fields['location'].widget.attrs.update({'class': 'form-select'})
        return form
    
    def get_success_url(self):
        if 'next' in self.request.POST:
            next_url = self.request.POST.get('next')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=[self.request.get_host()]):
                return next_url
        return reverse_lazy('inventory:equipment_item_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        previous_location = self.get_object().location
        result = super().form_valid(form)
        
        # Update status to 'assigned' if location is set, or 'available' if removed
        if form.instance.location:
            if form.instance.status not in ['maintenance', 'repair', 'retired']:
                form.instance.status = 'assigned'
                form.instance.save()
            location_name = form.instance.location.name
            messages.success(self.request, f"Equipment item '{form.instance.name}' has been assigned to {location_name}.")
        else:
            if form.instance.status == 'assigned':
                form.instance.status = 'available'
                form.instance.save()
            messages.success(self.request, f"Equipment item '{form.instance.name}' has been unassigned.")
        
        return result
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['next'] = self.request.GET.get('next', '')
        # Ensure equipment_item is available in template with both pk and id
        context['equipment_item'] = self.get_object()
        return context


@login_required
def update_equipment_status(request, pk):
    """View to update the status of an equipment item."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('inventory:equipment_item_list')
    
    equipment = get_object_or_404(EquipmentItem, pk=pk)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(EquipmentItem.STATUS_CHOICES):
            old_status = equipment.status
            
            # Handle status change to 'assigned'
            if new_status == 'assigned':
                location_id = request.POST.get('location')
                if location_id:
                    try:
                        location = SiteLocation.objects.get(id=location_id)
                        equipment.location = location
                        equipment.status = new_status
                        equipment.save()
                        messages.success(request, f"Status for '{equipment.name}' updated to Assigned and assigned to {location.name}.")
                    except SiteLocation.DoesNotExist:
                        messages.error(request, "Selected location does not exist.")
                        return redirect('inventory:equipment_item_assign', pk=equipment.pk)
                else:
                    # If no location provided, redirect to assignment page
                    messages.warning(request, f"Please select a location before setting the status to 'Assigned'.")
                    return redirect('inventory:equipment_item_assign', pk=equipment.pk)
            else:
                # Handle other status changes
                equipment.status = new_status
                equipment.save()
                
                # If status changes to available and it was assigned, remove location
                if new_status == 'available' and old_status == 'assigned':
                    equipment.location = None
                    equipment.save()
                    
                messages.success(request, f"Status for '{equipment.name}' updated to {dict(EquipmentItem.STATUS_CHOICES)[new_status]}.")
            
            # Redirect back based on the referring page
            next_url = request.POST.get('next', '')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=[request.get_host()]):
                return redirect(next_url)
            return redirect('inventory:equipment_item_detail', pk=equipment.pk)
        else:
            messages.error(request, "Invalid status selected.")
    
    # If not POST or invalid status, redirect to detail view
    return redirect('inventory:equipment_item_detail', pk=equipment.pk)

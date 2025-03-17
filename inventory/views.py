from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, TemplateView, FormView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Employee, Uniform, Transaction, ReturnRecord, TransactionItem, MultiItemTransaction, ItemReturnRecord
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
import io
from xhtml2pdf import pisa
from django.utils import timezone
from django.db.models import Sum, Count, Q, F
from .forms import ReturnTransactionForm, MultiItemTransactionForm, TransactionItemFormSet, SearchForm, CustomUserCreationForm, UserRoleForm, ImportFileForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.generic.edit import FormView, UpdateView
import datetime
from django.contrib.auth.models import User
import pandas as pd
from django.db import transaction, IntegrityError

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
                    Q(items__uniform__name__icontains=query)
                ).distinct()
            
            context['query'] = query
            context['search_type'] = search_type
            context['employees'] = employees
            context['uniforms'] = uniforms
            context['transactions'] = transactions
            context['has_results'] = employees.exists() or uniforms.exists() or transactions.exists()
        
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
        context['total_uniforms'] = Uniform.objects.count()
        
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
            
            # Now, save the formset
            item_formset.instance = transaction
            item_formset.save()
            
            # Update stock quantities for each uniform
            for item_form in item_formset:
                if item_form.cleaned_data and not item_form.cleaned_data.get('DELETE', False):
                    uniform = item_form.cleaned_data['uniform']
                    quantity = item_form.cleaned_data['quantity']
                    
                    # Check if there's enough stock
                    if uniform.stock_quantity < quantity:
                        messages.error(self.request, f'Not enough {uniform.name} in stock. Available: {uniform.stock_quantity}')
                        # Delete the transaction since we can't fulfill it
                        transaction.delete()
                        return self.form_invalid(form)
                    
                    # Reduce the stock quantity
                    uniform.stock_quantity -= quantity
                    uniform.save()
            
            # Create a more descriptive success message
            employee = transaction.employee
            employee_name = f"{employee.first_name} {employee.last_name}" if employee.first_name and employee.last_name else employee.employee_id
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
    
    context = {
        'employee': employee,
        'transactions': transactions,
        'now': timezone.now(),
        'total_items': total_items,
        'returned_items': total_returned,
        'outstanding_items': total_items - total_returned,
        'total_value': total_value,
        'outstanding_value': outstanding_value
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
def import_uniforms(request):
    """View to handle importing uniforms from Excel file."""
    if request.method == 'POST':
        form = ImportFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Process the Excel file
                excel_file = request.FILES['file']
                df = pd.read_excel(excel_file)
                
                # Validate required columns
                required_columns = ['name', 'size', 'price', 'stock_quantity']
                for column in required_columns:
                    if column not in df.columns:
                        messages.error(request, f"Missing required column: {column}")
                        return redirect('inventory:import_uniforms')
                
                # Track results
                success_count = 0
                error_count = 0
                errors = []
                
                # Process each row in the dataframe
                with transaction.atomic():
                    for index, row in df.iterrows():
                        try:
                            # Extract data from the row
                            name = str(row['name']).strip()
                            size = str(row['size']).strip()
                            
                            # Skip blank rows
                            if not name or not size:
                                continue
                            
                            # Convert price and quantities to correct types
                            try:
                                price = float(row['price'])
                                stock_quantity = int(row['stock_quantity']) if pd.notna(row['stock_quantity']) else 0
                                damaged_quantity = int(row.get('damaged_quantity', 0)) if pd.notna(row.get('damaged_quantity', 0)) else 0
                            except ValueError:
                                error_count += 1
                                errors.append(f"Row {index+2}: Invalid numeric values")
                                continue
                            
                            # Check if uniform already exists
                            uniform, created = Uniform.objects.update_or_create(
                                name=name,
                                size=size,
                                defaults={
                                    'price': price,
                                    'stock_quantity': stock_quantity,
                                    'damaged_quantity': damaged_quantity
                                }
                            )
                            
                            if created:
                                success_count += 1
                            else:
                                # Updated existing uniform
                                success_count += 1
                                
                        except IntegrityError:
                            error_count += 1
                            errors.append(f"Row {index+2}: Duplicate entry for {name} - {size}")
                        except Exception as e:
                            error_count += 1
                            errors.append(f"Row {index+2}: {str(e)}")
                
                # Report results
                if success_count > 0:
                    messages.success(request, f"Successfully imported {success_count} uniforms.")
                if error_count > 0:
                    messages.warning(request, f"Encountered {error_count} errors during import.")
                    for error in errors[:10]:  # Show first 10 errors
                        messages.error(request, error)
                    if len(errors) > 10:
                        messages.error(request, f"... and {len(errors) - 10} more errors.")
                
                return redirect('inventory:uniform_list')
            
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
    else:
        form = ImportFileForm()
    
    return render(request, 'inventory/import_uniforms.html', {'form': form})

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

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def export_uniform_template(request):
    """Generate a template Excel file for uniform imports."""
    # Create a DataFrame with the column headers
    df = pd.DataFrame(columns=['name', 'size', 'price', 'stock_quantity', 'damaged_quantity'])
    
    # Add sample data
    sample_data = [
        {'name': 'Shirt', 'size': 'M', 'price': 25.99, 'stock_quantity': 50, 'damaged_quantity': 0},
        {'name': 'Pants', 'size': 'L', 'price': 35.50, 'stock_quantity': 30, 'damaged_quantity': 2}
    ]
    df = pd.concat([df, pd.DataFrame(sample_data)], ignore_index=True)
    
    # Create a response with the Excel file
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=uniform_import_template.xlsx'
    
    # Write the DataFrame to the response
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Uniforms')
    
    return response

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

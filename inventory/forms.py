from django import forms
from django.forms import inlineformset_factory
from .models import Transaction, MultiItemTransaction, TransactionItem, Employee, Uniform, ReturnRecord
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.core.validators import FileExtensionValidator

class SearchForm(forms.Form):
    query = forms.CharField(
        label="Search",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search employees, uniforms...',
            'aria-label': 'Search'
        })
    )
    search_type = forms.ChoiceField(
        label="Search Type",
        required=False,
        choices=[
            ('all', 'All'),
            ('employees', 'Employees'),
            ('uniforms', 'Uniforms'),
            ('transactions', 'Transactions')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class ReturnTransactionForm(forms.Form):
    all_returned = forms.ChoiceField(
        choices=(('yes', 'Yes, all items returned'), ('no', 'Partial return')),
        widget=forms.RadioSelect,
        label="Return Options",
        initial='yes'
    )
    returned_quantity = forms.IntegerField(
        required=False,
        min_value=1,
        label="If partial, how many items to return?",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    has_damaged_items = forms.BooleanField(
        required=False,
        label="Some returned items are damaged/unusable",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'has_damaged_items'
        })
    )
    damaged_quantity = forms.IntegerField(
        required=False,
        min_value=0,
        label="Number of damaged items",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'damaged_quantity'
        })
    )
    damage_type = forms.ChoiceField(
        required=False,
        choices=ReturnRecord.DAMAGE_TYPE_CHOICES,
        label="Type of damage",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'damage_type'
        })
    )
    damage_notes = forms.CharField(
        required=False,
        label="Damage description",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'id': 'damage_notes',
            'placeholder': 'Please describe the damage...'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        all_returned = cleaned_data.get("all_returned")
        returned_quantity = cleaned_data.get("returned_quantity")
        has_damaged_items = cleaned_data.get("has_damaged_items")
        damaged_quantity = cleaned_data.get("damaged_quantity")
        damage_type = cleaned_data.get("damage_type")
        
        if all_returned == 'no' and not returned_quantity:
            self.add_error("returned_quantity", "Please specify how many items were returned.")
        
        if has_damaged_items:
            if damaged_quantity is None:
                self.add_error("damaged_quantity", "Please specify how many items are damaged.")
            if not damage_type or damage_type == 'none':
                self.add_error("damage_type", "Please specify the type of damage.")
            if returned_quantity and damaged_quantity and damaged_quantity > returned_quantity:
                self.add_error("damaged_quantity", "Damaged quantity cannot exceed total returned quantity.")
                
        return cleaned_data

class MultiItemTransactionForm(forms.ModelForm):
    # Override the payment_option field to include a custom empty label
    payment_option = forms.ChoiceField(
        choices=[('', 'Select payment method')] + list(MultiItemTransaction.PAYMENT_OPTIONS),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = MultiItemTransaction
        fields = ['employee', 'payment_option', 'loaned']
        widgets = {
            'employee': forms.Select(attrs={
                'class': 'form-select',
                'placeholder': 'Select an employee'
            }),
            'loaned': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch',
                'aria-checked': 'false'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add better empty label for employee dropdown
        self.fields['employee'].empty_label = "Select an employee"
        
        # If there's an existing payment option value, preserve it
        if self.instance and self.instance.pk and self.instance.payment_option:
            self.fields['payment_option'].initial = self.instance.payment_option

class TransactionItemForm(forms.ModelForm):
    class Meta:
        model = TransactionItem
        fields = ['uniform', 'quantity', 'serial_number']
        widgets = {
            'uniform': forms.Select(attrs={
                'class': 'form-select',
                'placeholder': 'Select a uniform'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '1'
            }),
            'serial_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional: Enter serial number for tracked items'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add better empty label for uniform dropdown
        self.fields['uniform'].empty_label = "Select a uniform"
        # Make serial_number not required
        self.fields['serial_number'].required = False

# Create a formset for multiple TransactionItems
TransactionItemFormSet = inlineformset_factory(
    MultiItemTransaction, 
    TransactionItem,
    form=TransactionItemForm,
    extra=0,  # Number of empty forms to display (changed from 1 to 0)
    can_delete=True,
    min_num=1,  # Require at least one item
    validate_min=True
)

class CustomUserCreationForm(UserCreationForm):
    """
    A custom user creation form with simplified permission options.
    """
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add better labels and help text
        self.fields['username'].help_text = 'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'
        self.fields['email'].required = True
        self.fields['email'].help_text = 'Required. Enter a valid email address.'
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

class UserRoleForm(forms.Form):
    """
    A form for assigning roles to users with simplified permission options.
    """
    ROLE_CHOICES = [
        ('viewer', 'Viewer (View only access)'),
        ('staff', 'Staff (Can manage inventory and transactions)'),
        ('admin', 'Administrator (Full access)'),
    ]
    
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect,
        label="User Role",
        required=True,
        help_text="Select the appropriate role for this user."
    )
    
    def save(self, user):
        """
        Apply the selected role to the user.
        """
        role = self.cleaned_data['role']
        
        # Reset permissions
        user.is_staff = False
        user.is_superuser = False
        user.user_permissions.clear()
        
        # Apply role-specific permissions
        if role == 'viewer':
            # Viewer can only view data
            self._assign_view_permissions(user)
        elif role == 'staff':
            # Staff can manage inventory and transactions
            user.is_staff = True
            self._assign_staff_permissions(user)
        elif role == 'admin':
            # Admin has full access
            user.is_staff = True
            user.is_superuser = True
        
        user.save()
        return user
    
    def _assign_view_permissions(self, user):
        """Assign view-only permissions for all models."""
        # Get all content types for the inventory app
        content_types = ContentType.objects.filter(app_label='inventory')
        
        # Get all view permissions for these content types
        view_permissions = Permission.objects.filter(
            content_type__in=content_types,
            codename__startswith='view_'
        )
        
        # Assign permissions to user
        for perm in view_permissions:
            user.user_permissions.add(perm)
    
    def _assign_staff_permissions(self, user):
        """Assign staff-level permissions (everything except user management)."""
        # Get all content types for the inventory app
        content_types = ContentType.objects.filter(app_label='inventory')
        
        # Get all permissions for these content types
        inventory_permissions = Permission.objects.filter(content_type__in=content_types)
        
        # Assign permissions to user
        for perm in inventory_permissions:
            user.user_permissions.add(perm)

class ImportFileForm(forms.Form):
    """Form for uploading Excel files to import data."""
    file = forms.FileField(
        label='Select Excel File',
        help_text='Only Excel files (.xlsx, .xls) are supported',
        validators=[
            FileExtensionValidator(allowed_extensions=['xlsx', 'xls'])
        ]
    )
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.name.endswith(('.xlsx', '.xls')):
                raise forms.ValidationError('Unsupported file format. Please upload an Excel file (.xlsx, .xls).')
        return file

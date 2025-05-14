from django import forms
from django.forms import inlineformset_factory, formset_factory
from .models import Transaction, MultiItemTransaction, TransactionItem, Employee, Uniform, ReturnRecord, UniformType, UniformSize, SiteLocation, EquipmentItem
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError

class SearchForm(forms.Form):
    query = forms.CharField(
        label="Search",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search employees, uniforms, locations, equipment...',
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
            ('transactions', 'Transactions'),
            ('locations', 'Locations'),
            ('equipment', 'Equipment')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class ReturnTransactionForm(forms.Form):
    all_returned = forms.ChoiceField(
        choices=[('yes', 'Yes, all remaining items'), ('no', 'No, only some items')],
        widget=forms.RadioSelect,
        initial='no',
        required=True
    )
    
    returned_quantity = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    has_damaged_items = forms.BooleanField(
        required=False,
        initial=False
    )
    
    damaged_quantity = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    damage_type = forms.ChoiceField(
        choices=ReturnRecord.DAMAGE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    damage_notes = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Describe the damage (optional)'
        })
    )
    
    def clean_damage_notes(self):
        # Get the damage notes from the form
        damage_notes = self.cleaned_data.get('damage_notes', '')
        
        # Basic sanitization to prevent CSRF issues
        # Remove any potentially problematic characters
        import re
        damage_notes = re.sub(r'[<>]', '', damage_notes)
        
        # Limit to 500 characters
        return damage_notes[:500]
        
    def clean(self):
        cleaned_data = super().clean()
        all_returned = cleaned_data.get('all_returned')
        returned_quantity = cleaned_data.get('returned_quantity')
        has_damaged_items = cleaned_data.get('has_damaged_items')
        damaged_quantity = cleaned_data.get('damaged_quantity')
        
        # If not returning all items, require a quantity
        if all_returned == 'no' and not returned_quantity:
            self.add_error('returned_quantity', 'Please enter the number of items being returned.')
        
        # If has damaged items, require a damaged quantity
        if has_damaged_items and damaged_quantity is None:
            self.add_error('damaged_quantity', 'Please enter the number of damaged items.')
        
        # Make sure damaged quantity is not more than returned quantity
        if returned_quantity and damaged_quantity and damaged_quantity > returned_quantity:
            self.add_error('damaged_quantity', 'Damaged quantity cannot exceed the returned quantity.')
        
        return cleaned_data

class MultiItemTransactionForm(forms.ModelForm):
    # Override the payment_option field to include a custom empty label
    payment_option = forms.ChoiceField(
        choices=[('', 'Select payment method')] + list(MultiItemTransaction.PAYMENT_OPTIONS),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'aria-label': 'Select payment method'
        }),
        error_messages={
            'required': 'Please select a payment method',
            'invalid_choice': 'Please select a valid payment method'
        }
    )
    
    class Meta:
        model = MultiItemTransaction
        fields = ['employee', 'payment_option', 'loaned', 'notes', 'is_prior_record']
        widgets = {
            'employee': forms.Select(attrs={
                'class': 'form-select',
                'placeholder': 'Select an employee',
                'aria-label': 'Select employee'
            }),
            'loaned': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch',
                'aria-checked': 'false'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter transaction notes, including serial numbers for items',
                'aria-label': 'Transaction notes'
            }),
            'is_prior_record': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch',
                'aria-checked': 'false'
            }),
        }
        labels = {
            'is_prior_record': 'Prior Record',
        }
        help_texts = {
            'is_prior_record': 'Check this box for uniforms issued before implementation of this system.'
        }
        error_messages = {
            'employee': {
                'required': 'Please select an employee',
                'invalid_choice': 'Please select a valid employee'
            }
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add better empty label for employee dropdown
        self.fields['employee'].empty_label = "Select an employee"
        
        # If there's an existing payment option value, preserve it
        if self.instance and self.instance.pk and self.instance.payment_option:
            self.fields['payment_option'].initial = self.instance.payment_option
            
        # Add error class to fields with errors
        for field_name, field in self.fields.items():
            if field.required:
                field.widget.attrs['required'] = 'required'
            if self.errors.get(field_name):
                if isinstance(field.widget, forms.Select):
                    field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' is-invalid'
                elif isinstance(field.widget, forms.TextInput) or isinstance(field.widget, forms.Textarea):
                    field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' is-invalid'

class TransactionItemForm(forms.ModelForm):
    """Form for TransactionItem model."""
    
    uniform_type = forms.ModelChoiceField(
        queryset=UniformType.objects.all().order_by('name'),
        required=False,
        empty_label="Select uniform type",
        widget=forms.Select(attrs={
            'class': 'form-select uniform-type-select',
            'aria-label': 'Select uniform type'
        })
    )
    
    size = forms.CharField(
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select size-select',
            'aria-label': 'Select size'
        })
    )
    
    uniform = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )
    
    class Meta:
        model = TransactionItem
        fields = ['uniform', 'quantity']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'value': '1',
                'aria-label': 'Quantity'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If we're editing an existing transaction item
        if self.instance and self.instance.pk and self.instance.uniform:
            uniform = self.instance.uniform
            self.fields['uniform_type'].initial = uniform.uniform_type
            self.fields['size'].initial = uniform.size
            self.fields['uniform'].initial = uniform.id
            
        # Add error class to fields with errors
        for field_name, field in self.fields.items():
            if field.required:
                field.widget.attrs['required'] = 'required'
            if self.errors.get(field_name):
                if isinstance(field.widget, forms.Select):
                    field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' is-invalid'
                elif isinstance(field.widget, forms.NumberInput):
                    field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' is-invalid'
    
    def clean(self):
        cleaned_data = super().clean()
        uniform_id = cleaned_data.get('uniform')
        
        # If we have a uniform ID, convert it to a Uniform object
        if uniform_id:
            try:
                uniform = Uniform.objects.get(id=uniform_id)
                # Replace the ID with the actual Uniform object
                cleaned_data['uniform'] = uniform
            except Uniform.DoesNotExist:
                raise ValidationError({
                    'uniform_type': "The selected uniform does not exist.",
                    'size': "The selected uniform does not exist."
                })
        else:
            # Try to find the uniform by type and size
            uniform_type = cleaned_data.get('uniform_type')
            size = cleaned_data.get('size')
            
            if uniform_type and size:
                try:
                    uniform = Uniform.objects.get(uniform_type=uniform_type, size=size)
                    cleaned_data['uniform'] = uniform
                except Uniform.DoesNotExist:
                    raise ValidationError({
                        'uniform_type': "No uniform found with this type and size.",
                        'size': "No uniform found with this type and size."
                    })
            else:
                if not uniform_type:
                    raise ValidationError({
                        'uniform_type': "Please select a uniform type."
                    })
                if not size:
                    raise ValidationError({
                        'size': "Please select a size."
                    })
        
        return cleaned_data

# Create a formset for multiple TransactionItems
TransactionItemFormSet = inlineformset_factory(
    MultiItemTransaction, 
    TransactionItem,
    form=TransactionItemForm,
    extra=0,  # Number of empty forms to display
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

class UniformTypeForm(forms.ModelForm):
    class Meta:
        model = UniformType
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class UniformSizeForm(forms.ModelForm):
    class Meta:
        model = UniformSize
        fields = ['name', 'display_order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class UniformWithSizesForm(forms.Form):
    uniform_type = forms.ModelChoiceField(
        queryset=UniformType.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select a uniform type or enter a new one"
    )
    new_uniform_type = forms.CharField(
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Or enter a new uniform type name'
        })
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Description (optional)'
        }),
        required=False
    )
    price = forms.DecimalField(
        max_digits=6, 
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Price for all sizes'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically add size fields based on available sizes
        sizes = UniformSize.objects.all()
        if not sizes.exists():
            # Create default sizes if none exist
            default_sizes = [
                ('Small', 1),
                ('Medium', 2),
                ('Large', 3),
                ('X-Large', 4),
                ('2XL', 5),
                ('3XL', 6),
            ]
            for size_name, display_order in default_sizes:
                UniformSize.objects.create(name=size_name, display_order=display_order)
            sizes = UniformSize.objects.all()
            
        # Add fields for each size
        for size in sizes:
            field_name = f'quantity_{size.id}'
            self.fields[field_name] = forms.IntegerField(
                required=False,
                min_value=0,
                initial=0,
                label=size.name,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control size-quantity',
                    'placeholder': f'Quantity for {size.name}'
                })
            )
            
    def clean(self):
        cleaned_data = super().clean()
        uniform_type = cleaned_data.get('uniform_type')
        new_uniform_type = cleaned_data.get('new_uniform_type')
        
        # Either an existing uniform type or a new one must be specified
        if not uniform_type and not new_uniform_type:
            self.add_error('uniform_type', 'Please select an existing uniform type or enter a new one.')
            
        # Check that at least one size has a quantity
        has_quantity = False
        for field_name, value in cleaned_data.items():
            if field_name.startswith('quantity_') and value and value > 0:
                has_quantity = True
                break
                
        if not has_quantity:
            self.add_error(None, 'Please specify a quantity for at least one size.')
            
        return cleaned_data

    @property
    def size_fields(self):
        """Return a list of size quantity fields in display order"""
        size_fields = []
        sizes = UniformSize.objects.all().order_by('display_order')
        for size in sizes:
            field_name = f'quantity_{size.id}'
            if field_name in self.fields:
                size_fields.append(self[field_name])
        return size_fields

# Add the SiteLocationForm below
class SiteLocationForm(forms.ModelForm):
    """Form for creating and updating site locations."""
    class Meta:
        model = SiteLocation
        fields = ['name', 'address', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Location name (e.g. Main Office, Warehouse A)',
            }),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Physical address (optional)',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief description of this location',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch',
            }),
        }
        labels = {
            'is_active': 'Active Location',
        }
        help_texts = {
            'is_active': 'Inactive locations will not appear in assignment dropdown lists',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add validation classes for Bootstrap
        for field_name, field in self.fields.items():
            if field.required:
                field.widget.attrs['required'] = 'required'
            if self.errors.get(field_name):
                if isinstance(field.widget, forms.Select):
                    field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' is-invalid'
                elif isinstance(field.widget, forms.TextInput) or isinstance(field.widget, forms.Textarea):
                    field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' is-invalid'

# Add more forms as needed below

class EquipmentItemForm(forms.ModelForm):
    """Form for creating and updating equipment items."""
    
    class Meta:
        model = EquipmentItem
        fields = [
            'name', 'category', 'serial_number', 'asset_tag', 
            'purchase_date', 'purchase_price', 'status', 
            'last_maintenance_date', 'location', 'description', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter equipment name'
            }),
            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category (e.g., Computer, Tool, Machinery)'
            }),
            'serial_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter serial number (optional)'
            }),
            'asset_tag': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter asset tag (optional)'
            }),
            'purchase_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'purchase_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter purchase price',
                'step': '0.01'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'last_maintenance_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'location': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter equipment description'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter additional notes'
            }),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter locations to only active ones
        self.fields['location'].queryset = SiteLocation.objects.filter(is_active=True)
        self.fields['location'].empty_label = "Select a location (optional)"
        
        # Add error class to fields with errors
        for field_name, field in self.fields.items():
            if field.required:
                field.widget.attrs['required'] = 'required'
            if self.errors.get(field_name):
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' is-invalid'

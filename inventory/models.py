from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum
from django.core.validators import MinValueValidator

class Employee(models.Model):
    employee_id = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_archived = models.BooleanField(default=False, help_text="Whether this employee has been archived")
    archive_date = models.DateTimeField(blank=True, null=True, help_text="When this employee was archived")
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.employee_id})"
    
    def total_outstanding_balance(self):
        """Calculate the total balance from all unpaid transactions."""
        # Calculate balance from regular transactions
        regular_balance = self.transaction_set.filter(
            loaned=True, returned=False
        ).aggregate(
            total=Sum(models.F('quantity') * models.F('uniform__price'))
        )['total'] or 0
        
        # Calculate balance from multi-item transactions
        multi_balance = sum(
            transaction.total_cost() 
            for transaction in self.multiitemtransaction_set.filter(loaned=True, returned=False)
        )
        
        return regular_balance + multi_balance

class Uniform(models.Model):
    name = models.CharField(max_length=100)
    size = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    damaged_quantity = models.PositiveIntegerField(default=0, help_text="Number of damaged/unusable items in inventory")
    
    def __str__(self):
        return f"{self.name} - {self.size} (${self.price})"
    
    @property
    def usable_quantity(self):
        """Returns the number of items that are usable (not damaged)."""
        return self.stock_quantity - self.damaged_quantity
    
    class Meta:
        unique_together = ('name', 'size')

class Transaction(models.Model):
    PAYMENT_OPTIONS = [
        ('cash', 'Cash'),
        ('credit_card', 'Credit Card'),
        ('payroll_deduction', 'Payroll Deduction'),
        ('no_charge', 'No Charge'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    uniform = models.ForeignKey(Uniform, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    transaction_date = models.DateTimeField(auto_now_add=True)
    payment_option = models.CharField(max_length=20, choices=PAYMENT_OPTIONS)
    loaned = models.BooleanField(default=False)
    returned = models.BooleanField(default=False)
    return_date = models.DateTimeField(null=True, blank=True)
    
    @property
    def total_returned(self):
        """Calculate the total quantity that has been returned for this transaction."""
        return self.returnrecord_set.aggregate(total=Sum('returned_quantity'))['total'] or 0
    
    def total_cost(self):
        """Calculate the total cost of the transaction."""
        return self.quantity * self.uniform.price
    
    def __str__(self):
        return f"Transaction {self.id} - {self.employee} - {self.quantity} {self.uniform.name}"

class ReturnRecord(models.Model):
    DAMAGE_TYPE_CHOICES = [
        ('none', 'No Damage'),
        ('wear', 'Normal Wear and Tear'),
        ('incident', 'Work Incident'),
        ('other', 'Other Damage'),
    ]
    
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, null=True, blank=True)
    returned_quantity = models.PositiveIntegerField()
    return_date = models.DateTimeField(auto_now_add=True)
    damaged_quantity = models.PositiveIntegerField(default=0, help_text="Number of returned items that are damaged/unusable")
    damage_type = models.CharField(max_length=10, choices=DAMAGE_TYPE_CHOICES, default='none')
    damage_notes = models.TextField(blank=True, null=True, help_text="Description of damage if applicable")
    
    def __str__(self):
        return f"Return for Transaction {self.transaction.id if self.transaction else 'None'} - {self.returned_quantity} items"

# New models for multi-item transactions
class MultiItemTransaction(models.Model):
    PAYMENT_OPTIONS = [
        ('cash', 'Cash'),
        ('credit_card', 'Credit Card'),
        ('payroll_deduction', 'Payroll Deduction'),
        ('no_charge', 'No Charge'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    transaction_date = models.DateTimeField(auto_now_add=True)
    payment_option = models.CharField(max_length=20, choices=PAYMENT_OPTIONS)
    loaned = models.BooleanField(default=False)
    returned = models.BooleanField(default=False)
    return_date = models.DateTimeField(null=True, blank=True)
    
    def total_cost(self):
        """Calculate the total cost of all items in this transaction."""
        return sum(item.total_cost() for item in self.items.all())
    
    @property
    def is_fully_returned(self):
        """Check if all items in this transaction have been fully returned."""
        for item in self.items.all():
            if item.total_returned < item.quantity:
                return False
        return True
    
    def __str__(self):
        return f"Multi-Item Transaction {self.id} - {self.employee}"

class TransactionItem(models.Model):
    transaction = models.ForeignKey(MultiItemTransaction, on_delete=models.CASCADE, related_name='items')
    uniform = models.ForeignKey(Uniform, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    serial_number = models.CharField(max_length=100, null=True, blank=True, 
                                    help_text="Serial number for tracked items")
    
    def total_cost(self):
        return self.uniform.price * self.quantity
    
    def total_returned(self):
        return sum(record.quantity_returned for record in self.return_records.all())
    
    def __str__(self):
        return f"{self.quantity} x {self.uniform.name} ({self.uniform.size})"

class ItemReturnRecord(models.Model):
    DAMAGE_TYPE_CHOICES = [
        ('none', 'No Damage'),
        ('wear', 'Normal Wear and Tear'),
        ('incident', 'Work Incident'),
        ('other', 'Other Damage'),
    ]
    
    transaction_item = models.ForeignKey(TransactionItem, on_delete=models.CASCADE)
    returned_quantity = models.PositiveIntegerField()
    return_date = models.DateTimeField(auto_now_add=True)
    damaged_quantity = models.PositiveIntegerField(default=0, help_text="Number of returned items that are damaged/unusable")
    damage_type = models.CharField(max_length=10, choices=DAMAGE_TYPE_CHOICES, default='none')
    damage_notes = models.TextField(blank=True, null=True, help_text="Description of damage if applicable")
    
    def __str__(self):
        return f"Return for Item {self.transaction_item.id} - {self.returned_quantity} items"

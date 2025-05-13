from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from inventory.models import (
    UniformType, UniformSize, Uniform, Employee, MultiItemTransaction,
    TransactionItem, SiteLocation, EquipmentItem
)
import random
from django.contrib.auth.models import User
import datetime


class Command(BaseCommand):
    help = 'Populates the database with sample data for testing and demos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--employees',
            default=20,
            type=int,
            help='Number of employees to create'
        )
        parser.add_argument(
            '--transactions',
            default=30,
            type=int,
            help='Number of transactions to create'
        )
        parser.add_argument(
            '--equipment',
            default=15,
            type=int,
            help='Number of equipment items to create'
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting data population...')
        
        # Get the number of items to create from command arguments
        num_employees = options['employees']
        num_transactions = options['transactions']
        num_equipment = options['equipment']
        
        # Use a transaction to ensure all-or-nothing
        with transaction.atomic():
            self.create_uniform_types_and_sizes()
            self.create_uniforms()
            employees = self.create_employees(num_employees)
            self.create_transactions(employees, num_transactions)
            self.create_site_locations_and_equipment(num_equipment)
            
        self.stdout.write(self.style.SUCCESS('Successfully populated database with sample data!'))

    def create_uniform_types_and_sizes(self):
        """Create uniform types and sizes"""
        self.stdout.write('Creating uniform types and sizes...')
        
        # Create uniform types
        uniform_types = [
            {'name': 'Shirts', 'description': 'All types of shirts'},
            {'name': 'Pants', 'description': 'Work pants and trousers'},
            {'name': 'Safety Vests', 'description': 'High visibility safety vests'},
            {'name': 'Jackets', 'description': 'Weather-resistant jackets for outdoor work'},
            {'name': 'Boots', 'description': 'Safety boots and footwear'},
            {'name': 'Gloves', 'description': 'Work gloves for various tasks'},
            {'name': 'Headwear', 'description': 'Hats, helmets, and other head protection'},
        ]
        
        for i, type_data in enumerate(uniform_types):
            uniform_type, created = UniformType.objects.get_or_create(
                name=type_data['name'],
                defaults={'description': type_data['description']}
            )
            if created:
                self.stdout.write(f"  Created uniform type: {uniform_type.name}")
        
        # Create uniform sizes with display order
        sizes = [
            {'name': 'XS', 'display_order': 1},
            {'name': 'S', 'display_order': 2},
            {'name': 'M', 'display_order': 3},
            {'name': 'L', 'display_order': 4},
            {'name': 'XL', 'display_order': 5},
            {'name': '2XL', 'display_order': 6},
            {'name': '3XL', 'display_order': 7},
            {'name': '4XL', 'display_order': 8},
            {'name': '5XL', 'display_order': 9},
            {'name': '6', 'display_order': 10},
            {'name': '7', 'display_order': 11},
            {'name': '8', 'display_order': 12},
            {'name': '9', 'display_order': 13},
            {'name': '10', 'display_order': 14},
            {'name': '11', 'display_order': 15},
            {'name': '12', 'display_order': 16},
        ]
        
        for size_data in sizes:
            size, created = UniformSize.objects.get_or_create(
                name=size_data['name'],
                defaults={'display_order': size_data['display_order']}
            )
            if created:
                self.stdout.write(f"  Created uniform size: {size.name}")

    def create_uniforms(self):
        """Create uniforms with various types and sizes"""
        self.stdout.write('Creating uniforms...')
        
        types = UniformType.objects.all()
        sizes = UniformSize.objects.all()
        
        # Dictionary to define uniforms with their properties
        uniform_definitions = {
            'Shirts': {
                'variants': ['Long Sleeve Work Shirt', 'Short Sleeve Polo', 'Button-Down Shirt'],
                'sizes': ['XS', 'S', 'M', 'L', 'XL', '2XL', '3XL'],
                'price_range': (24.99, 39.99),
                'stock_range': (10, 50)
            },
            'Pants': {
                'variants': ['Cargo Pants', 'Work Jeans', 'Khaki Pants'],
                'sizes': ['30', '32', '34', '36', '38', '40', '42'],
                'price_range': (34.99, 59.99),
                'stock_range': (8, 40)
            },
            'Safety Vests': {
                'variants': ['Class 2 Safety Vest', 'Class 3 High-Vis Vest', 'Reflective Vest'],
                'sizes': ['S', 'M', 'L', 'XL', '2XL', '3XL'],
                'price_range': (19.99, 29.99),
                'stock_range': (15, 60)
            },
            'Jackets': {
                'variants': ['Winter Jacket', 'Rain Jacket', 'Lightweight Jacket'],
                'sizes': ['S', 'M', 'L', 'XL', '2XL', '3XL'],
                'price_range': (49.99, 89.99),
                'stock_range': (5, 30)
            },
            'Boots': {
                'variants': ['Steel Toe Boots', 'Waterproof Work Boots', 'Composite Toe Boots'],
                'sizes': ['7', '8', '9', '10', '11', '12'],
                'price_range': (79.99, 129.99),
                'stock_range': (3, 20)
            },
            'Gloves': {
                'variants': ['Leather Work Gloves', 'Cut-Resistant Gloves', 'Heat-Resistant Gloves'],
                'sizes': ['S', 'M', 'L', 'XL'],
                'price_range': (12.99, 24.99),
                'stock_range': (10, 50)
            },
            'Headwear': {
                'variants': ['Hard Hat', 'Baseball Cap', 'Beanie'],
                'sizes': ['One Size', 'S/M', 'L/XL'],
                'price_range': (9.99, 29.99),
                'stock_range': (10, 40)
            }
        }
        
        # Create uniforms based on the defined types and sizes
        uniform_count = 0
        for type_obj in types:
            if type_obj.name in uniform_definitions:
                definition = uniform_definitions[type_obj.name]
                
                for variant in definition['variants']:
                    for size_name in definition['sizes']:
                        # Get the size object if it exists
                        size_obj = None
                        try:
                            size_obj = sizes.get(name=size_name)
                        except UniformSize.DoesNotExist:
                            continue
                        
                        # Generate random price and stock quantity
                        price = round(random.uniform(*definition['price_range']), 2)
                        stock = random.randint(*definition['stock_range'])
                        damaged = random.randint(0, max(1, stock // 10))  # 0-10% damaged
                        
                        # Create the uniform
                        uniform, created = Uniform.objects.get_or_create(
                            name=variant,
                            size=size_obj.name,
                            defaults={
                                'uniform_type': type_obj,
                                'price': price,
                                'stock_quantity': stock,
                                'damaged_quantity': damaged
                            }
                        )
                        
                        if created:
                            uniform_count += 1
                            if uniform_count % 5 == 0:  # Log every 5th item to avoid too much output
                                self.stdout.write(f"  Created uniform: {uniform.name} - {uniform.size} (${uniform.price})")
        
        self.stdout.write(f"  Created {uniform_count} uniforms in total")

    def create_employees(self, count):
        """Create sample employees"""
        self.stdout.write(f'Creating {count} employees...')
        
        first_names = [
            'James', 'Mary', 'John', 'Patricia', 'Robert', 'Jennifer', 'Michael', 'Linda',
            'William', 'Elizabeth', 'David', 'Barbara', 'Richard', 'Susan', 'Joseph',
            'Jessica', 'Thomas', 'Sarah', 'Charles', 'Karen', 'Christopher', 'Nancy',
            'Daniel', 'Lisa', 'Matthew', 'Margaret', 'Anthony', 'Betty', 'Mark', 'Sandra',
            'Donald', 'Ashley', 'Steven', 'Kimberly', 'Paul', 'Donna', 'Andrew', 'Emily',
            'Joshua', 'Michelle', 'Kenneth', 'Amanda', 'Kevin', 'Dorothy', 'Brian', 'Melissa',
            'George', 'Deborah', 'Edward', 'Stephanie'
        ]
        
        last_names = [
            'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller', 'Davis', 'Garcia',
            'Rodriguez', 'Wilson', 'Martinez', 'Anderson', 'Taylor', 'Thomas', 'Hernandez',
            'Moore', 'Martin', 'Jackson', 'Thompson', 'White', 'Lopez', 'Lee', 'Gonzalez',
            'Harris', 'Clark', 'Lewis', 'Robinson', 'Walker', 'Perez', 'Hall', 'Young',
            'Allen', 'Sanchez', 'Wright', 'King', 'Scott', 'Green', 'Baker', 'Adams',
            'Nelson', 'Hill', 'Ramirez', 'Campbell', 'Mitchell', 'Roberts', 'Carter',
            'Phillips', 'Evans', 'Turner', 'Torres'
        ]
        
        employees = []
        existing_ids = set(Employee.objects.values_list('employee_id', flat=True))
        
        for i in range(count):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            
            # Create a unique employee ID
            while True:
                employee_id = f"EMP{random.randint(1000, 9999)}"
                if employee_id not in existing_ids:
                    existing_ids.add(employee_id)
                    break
            
            email = f"{first_name.lower()}.{last_name.lower()}@example.com"
            phone = f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
            
            # Small chance of archived employee
            is_archived = random.random() < 0.1  # 10% chance
            archive_date = timezone.now() if is_archived else None
            
            employee = Employee.objects.create(
                employee_id=employee_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                is_archived=is_archived,
                archive_date=archive_date
            )
            
            employees.append(employee)
            self.stdout.write(f"  Created employee: {employee.first_name} {employee.last_name} ({employee.employee_id})")
        
        return employees

    def create_transactions(self, employees, count):
        """Create sample transactions"""
        self.stdout.write(f'Creating {count} transactions...')
        
        uniforms = list(Uniform.objects.all())
        payment_options = ['cash', 'credit_card', 'payroll_deduction', 'no_charge']
        
        if not uniforms:
            self.stdout.write("No uniforms available - skipping transaction creation")
            return
        
        # Generate dates in the past 90 days
        end_date = timezone.now()
        start_date = end_date - datetime.timedelta(days=90)
        
        for i in range(count):
            # Select a random employee (who is not archived)
            active_employees = [e for e in employees if not e.is_archived]
            if not active_employees:
                active_employees = employees  # Fallback if no active employees
                
            employee = random.choice(active_employees)
            
            # Generate a random date for the transaction
            days_ago = random.randint(0, 90)
            transaction_date = timezone.now() - datetime.timedelta(days=days_ago)
            
            # Create transaction
            payment = random.choice(payment_options)
            loaned = random.random() < 0.6  # 60% chance of being a loan
            returned = False
            return_date = None
            
            if loaned and random.random() < 0.3:  # 30% of loans have been returned
                returned = True
                return_date = transaction_date + datetime.timedelta(days=random.randint(1, 30))
            
            # Create multi-item transaction
            transaction = MultiItemTransaction.objects.create(
                employee=employee,
                transaction_date=transaction_date,
                payment_option=payment,
                loaned=loaned,
                returned=returned,
                return_date=return_date,
                notes=f"Sample transaction #{i+1} - {'Loan' if loaned else 'Purchase'}"
            )
            
            # Add 1-3 items to each transaction
            item_count = random.randint(1, 3)
            transaction_uniforms = random.sample(uniforms, item_count)
            
            for uniform in transaction_uniforms:
                quantity = random.randint(1, 3)
                
                # Create transaction item
                TransactionItem.objects.create(
                    transaction=transaction,
                    uniform=uniform,
                    quantity=quantity,
                    serial_number=f"SN{random.randint(10000, 99999)}" if random.random() < 0.3 else None
                )
            
            if i % 5 == 0:  # Log every 5th transaction
                self.stdout.write(f"  Created transaction for {employee.first_name} {employee.last_name} with {item_count} items")
    
    def create_site_locations_and_equipment(self, equipment_count):
        """Create site locations and equipment items"""
        self.stdout.write('Creating site locations and equipment...')
        
        # Create site locations
        locations = [
            {"name": "Main Office", "address": "123 Main St, Springfield, IL", "description": "Company headquarters"},
            {"name": "Warehouse A", "address": "456 Industrial Pkwy, Springfield, IL", "description": "Main storage facility"},
            {"name": "Warehouse B", "address": "789 Shipping Lane, Springfield, IL", "description": "Secondary storage facility"},
            {"name": "Production Plant", "address": "101 Factory Rd, Springfield, IL", "description": "Manufacturing facility"},
            {"name": "Distribution Center", "address": "200 Logistics Blvd, Springfield, IL", "description": "Central distribution hub"},
            {"name": "Remote Office North", "address": "333 Business Center, Chicago, IL", "description": "Northern regional office"},
            {"name": "Remote Office South", "address": "444 Commerce Dr, Carbondale, IL", "description": "Southern regional office"},
        ]
        
        location_objects = []
        for location_data in locations:
            location, created = SiteLocation.objects.get_or_create(
                name=location_data["name"],
                defaults={
                    "address": location_data["address"],
                    "description": location_data["description"]
                }
            )
            location_objects.append(location)
            if created:
                self.stdout.write(f"  Created location: {location.name}")
        
        # Create equipment items
        self.stdout.write(f'Creating {equipment_count} equipment items...')
        
        equipment_categories = [
            "Computer", "Printer", "Phone", "Scanner", "Projector", 
            "Forklift", "Pallet Jack", "Tool Set", "Safety Equipment",
            "Office Furniture", "Vehicle", "Generator", "HVAC Unit"
        ]
        
        status_choices = ["available", "assigned", "maintenance", "repair", "retired"]
        status_weights = [0.5, 0.3, 0.1, 0.05, 0.05]  # probability weights
        
        for i in range(equipment_count):
            category = random.choice(equipment_categories)
            status = random.choices(status_choices, weights=status_weights)[0]
            
            # Format name based on category
            if category == "Computer":
                name = f"{random.choice(['Desktop', 'Laptop', 'Workstation'])} #{i+1}"
            elif category == "Vehicle":
                name = f"{random.choice(['Truck', 'Van', 'Car'])} #{i+1}"
            else:
                name = f"{category} #{i+1}"
            
            # Purchase info
            days_ago = random.randint(30, 1095)  # 1 month to 3 years
            purchase_date = timezone.now().date() - datetime.timedelta(days=days_ago)
            purchase_price = round(random.uniform(100, 5000), 2)
            
            # Maintenance dates
            last_maintenance = None
            if random.random() < 0.7:  # 70% chance of having maintenance
                maint_days_ago = random.randint(1, 365)  # up to 1 year ago
                last_maintenance = timezone.now().date() - datetime.timedelta(days=maint_days_ago)
            
            # Serial and asset numbers
            serial_number = f"SN-{category[:3].upper()}-{random.randint(10000, 99999)}"
            asset_tag = f"AT{random.randint(1000, 9999)}"
            
            # Assign to a location (some may not be assigned)
            location = None
            if status != "available" and random.random() < 0.8:  # 80% chance of location assignment if not available
                location = random.choice(location_objects)
            
            equipment = EquipmentItem.objects.create(
                name=name,
                category=category,
                serial_number=serial_number,
                asset_tag=asset_tag,
                purchase_date=purchase_date,
                purchase_price=purchase_price,
                status=status,
                last_maintenance_date=last_maintenance,
                location=location,
                description=f"Standard {category.lower()} for company use",
                notes=f"Sample equipment item created for testing."
            )
            
            if i % 5 == 0:  # Log every 5th equipment item
                self.stdout.write(f"  Created equipment: {equipment.name} ({equipment.status})") 
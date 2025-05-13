from django.core.management.base import BaseCommand
from django.db import transaction
from inventory.models import (
    Employee, UniformType, UniformSize, Uniform, 
    SiteLocation, EquipmentItem
)
import random
from django.utils import timezone
import datetime

class Command(BaseCommand):
    help = 'Generates sample data for the inventory system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--employees',
            type=int,
            default=10,
            help='Number of employees to create'
        )
        parser.add_argument(
            '--uniforms',
            type=int,
            default=20,
            help='Number of uniforms to create'
        )
        parser.add_argument(
            '--locations',
            type=int,
            default=5,
            help='Number of site locations to create'
        )
        parser.add_argument(
            '--equipment',
            type=int,
            default=15,
            help='Number of equipment items to create'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before generating new data'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['clear']:
            self.clear_data()
            self.stdout.write(self.style.SUCCESS('Cleared existing data'))

        self.create_uniform_types_and_sizes()
        self.create_employees(options['employees'])
        self.create_uniforms(options['uniforms'])
        self.create_site_locations(options['locations'])
        self.create_equipment(options['equipment'])
        
        self.stdout.write(self.style.SUCCESS('Successfully generated sample data'))
    
    def clear_data(self):
        # Delete in a specific order to avoid constraint errors
        EquipmentItem.objects.all().delete()
        SiteLocation.objects.all().delete()
        Uniform.objects.all().delete()
        UniformType.objects.all().delete()
        UniformSize.objects.all().delete()
        Employee.objects.all().delete()
    
    def create_uniform_types_and_sizes(self):
        # Create uniform types
        uniform_types = [
            'Long Sleeve Shirts',
            'Short Sleeve Shirts',
            'Pants',
            'Shorts',
            'Jackets',
            'Safety Vests',
            'Boots',
            'Gloves'
        ]
        for type_name in uniform_types:
            UniformType.objects.get_or_create(
                name=type_name,
                defaults={'description': f'Standard issue {type_name.lower()}'}
            )
        
        # Create uniform sizes
        sizes = ['XS', 'S', 'M', 'L', 'XL', '2XL', '3XL']
        for i, size in enumerate(sizes):
            UniformSize.objects.get_or_create(
                name=size,
                defaults={'display_order': i}
            )
            
        self.stdout.write(self.style.SUCCESS(f'Created {len(uniform_types)} uniform types and {len(sizes)} sizes'))
    
    def create_employees(self, count):
        for i in range(1, count + 1):
            employee_id = f'EMP{i:04d}'
            first_name = random.choice([
                'John', 'Jane', 'Michael', 'Sarah', 'David', 'Lisa',
                'Robert', 'Patricia', 'James', 'Jennifer', 'Thomas', 'Mary'
            ])
            last_name = random.choice([
                'Smith', 'Jones', 'Williams', 'Brown', 'Davis', 'Miller',
                'Wilson', 'Moore', 'Taylor', 'Anderson', 'Jackson', 'Harris'
            ])
            email = f'{first_name.lower()}.{last_name.lower()}@example.com'
            
            Employee.objects.get_or_create(
                employee_id=employee_id,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone': f'555-{random.randint(100, 999)}-{random.randint(1000, 9999)}'
                }
            )
        
        self.stdout.write(self.style.SUCCESS(f'Created {count} employees'))
    
    def create_uniforms(self, count):
        uniform_types = list(UniformType.objects.all())
        sizes = list(UniformSize.objects.all())
        
        if not uniform_types or not sizes:
            self.stdout.write(self.style.WARNING('No uniform types or sizes found. Skipping uniform creation.'))
            return
        
        created = 0
        for _ in range(count):
            uniform_type = random.choice(uniform_types)
            size = random.choice(sizes)
            
            name = f"{uniform_type.name} - {random.choice(['Standard', 'Premium', 'Deluxe', 'Economy'])}"
            price = round(random.uniform(10.0, 100.0), 2)
            stock = random.randint(5, 100)
            damaged = random.randint(0, min(5, stock))
            
            # Try to create a unique uniform
            try:
                Uniform.objects.create(
                    uniform_type=uniform_type,
                    name=name,
                    size=size.name,
                    price=price,
                    stock_quantity=stock,
                    damaged_quantity=damaged
                )
                created += 1
            except:
                # Skip if we hit a unique constraint error
                pass
        
        self.stdout.write(self.style.SUCCESS(f'Created {created} uniforms'))
    
    def create_site_locations(self, count):
        for i in range(1, count + 1):
            name = f"Location {i}"
            address = f"{random.randint(100, 999)} Main St, Suite {random.randint(100, 999)}"
            
            SiteLocation.objects.get_or_create(
                name=name,
                defaults={
                    'address': address,
                    'description': f'Sample location {i} for equipment storage',
                    'is_active': random.choice([True, True, True, False])  # 75% active
                }
            )
        
        self.stdout.write(self.style.SUCCESS(f'Created {count} site locations'))
    
    def create_equipment(self, count):
        locations = list(SiteLocation.objects.all())
        
        if not locations:
            self.stdout.write(self.style.WARNING('No locations found. Skipping equipment creation.'))
            return
        
        categories = ['Tools', 'Safety Equipment', 'Electronics', 'Machinery', 'Vehicles']
        statuses = ['available', 'assigned', 'maintenance', 'repair', 'retired']
        
        for i in range(1, count + 1):
            category = random.choice(categories)
            name = f"{category} Item {i}"
            serial = f"SN-{random.randint(10000, 99999)}"
            asset_tag = f"AT-{random.randint(1000, 9999)}"
            
            # Random date in the last 5 years
            days_ago = random.randint(0, 5*365)
            purchase_date = timezone.now().date() - datetime.timedelta(days=days_ago)
            
            EquipmentItem.objects.create(
                name=name,
                category=category,
                serial_number=serial,
                asset_tag=asset_tag,
                purchase_date=purchase_date,
                purchase_price=round(random.uniform(100.0, 5000.0), 2),
                status=random.choice(statuses),
                location=random.choice(locations) if random.random() > 0.2 else None,  # 80% assigned to a location
                description=f"Sample {category.lower()} item for testing",
                notes="Created by sample data generation script"
            )
        
        self.stdout.write(self.style.SUCCESS(f'Created {count} equipment items')) 
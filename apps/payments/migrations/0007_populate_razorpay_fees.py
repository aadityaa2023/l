"""
Data migration to calculate and set Razorpay fees for existing completed payments
"""
from django.db import migrations
from decimal import Decimal, ROUND_HALF_UP


def calculate_fees_for_existing_payments(apps, schema_editor):
    """Calculate and set Razorpay fees for all completed payments"""
    Payment = apps.get_model('payments', 'Payment')
    
    # Get all completed payments
    completed_payments = Payment.objects.filter(status='completed')
    
    updated_count = 0
    for payment in completed_payments:
        # Skip if already calculated
        if payment.net_amount and payment.net_amount > 0:
            continue
        
        # Convert amount to Decimal for precise calculation
        gross_amount = Decimal(str(payment.amount))
        
        # Calculate Razorpay fee (2%)
        razorpay_fee_rate = Decimal('0.02')  # 2%
        razorpay_fee = (gross_amount * razorpay_fee_rate).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        # Calculate GST on Razorpay fee (18%)
        gst_rate = Decimal('0.18')  # 18%
        razorpay_gst = (razorpay_fee * gst_rate).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        # Calculate net amount
        net_amount = gross_amount - razorpay_fee - razorpay_gst
        net_amount = net_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Update payment
        payment.razorpay_fee = razorpay_fee
        payment.razorpay_gst = razorpay_gst
        payment.net_amount = net_amount
        payment.save(update_fields=['razorpay_fee', 'razorpay_gst', 'net_amount'])
        
        updated_count += 1
    
    print(f"Updated {updated_count} existing payments with Razorpay fee calculations")


def reverse_fees(apps, schema_editor):
    """Reverse the migration by clearing the fee fields"""
    Payment = apps.get_model('payments', 'Payment')
    
    Payment.objects.all().update(
        razorpay_fee=0,
        razorpay_gst=0,
        net_amount=0
    )


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0006_add_razorpay_fee_fields'),
    ]

    operations = [
        migrations.RunPython(
            calculate_fees_for_existing_payments,
            reverse_fees
        ),
    ]

from django.db import models
# from django.template.defaultfilters import date
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils.translation import gettext_lazy as _
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
import json
import pandas as pd
import traceback
from django.db import transaction
import csv
from django.db.models import F, Q
from datetime import datetime
import pytz
from simple_history.models import HistoricalRecords
from simple_history import register
# from .utils import format_date_db_to_qrcode as format_date


# tracking changes to the User model
register(User)


# converts 1900-12-01 date format to Dec. 1, 1900 format, as found in qr code
def format_date_db_to_qrcode(input_date):
    date_object_to_formatted_string = input_date.date().strftime("%b. %-d, %Y")
    return date_object_to_formatted_string


class Vendor(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.CharField(max_length=200, unique=True)
    account_number = models.CharField(max_length=200, default="N/A")
    contact_email = models.EmailField(default="notyetadded@example.com")
    contact_phone = models.CharField(max_length=50, default="800-111-9999")
    abbrev = models.CharField(max_length=50, unique=True)
    last_ordered = models.DateTimeField(auto_now=False, null=True)
    notes = models.JSONField(default=list, blank=True)
    url = models.URLField(max_length=200, default="www.example.com/not-yet-applicable")
    history = HistoricalRecords()

    def __str__(self) -> str:
        return self.name

BOOL_CHOICES = ((True, 'Yes'), (False, 'No'))

class Product(models.Model):
    id = models.BigAutoField(
        auto_created=True,
        primary_key=True,
        unique=True,
        serialize=False,
        verbose_name="product_id",
    )
    name = models.CharField(max_length=300)
    reference_id = models.CharField(max_length=100)
    expiry_date = models.DateTimeField(auto_now=False, auto_now_add=False)
    ref_id_lot_number_expiry_date = models.CharField(max_length=250, unique=True)
    qr_code = models.CharField(max_length=350, unique=True)
    is_purchased = models.BooleanField(choices=BOOL_CHOICES, default=True)
    size = models.CharField(max_length=60, default="N/A", blank=True)
    barcode = models.CharField(max_length=300, default="N/A", blank=True, null=True)
    lot_number = models.CharField(max_length=300, default="N/A", blank=True, null=True)
    quantity_on_hand = models.PositiveIntegerField(default=1)
    quantity_on_order = models.PositiveIntegerField(default=0)
    date_added = models.DateTimeField(auto_now=False, auto_now_add=True, null=True)
    last_modified = models.DateTimeField(auto_now=False, null=True)
    employee = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    notes = models.JSONField(default=list, blank=True)
    history = HistoricalRecords()
    #{{product.name}}-{{product.barcode}}-{{product.expiry_date.date}}-{{product.lot_number}}
    def save(self, *args, **kwargs):
        self.qr_code = self.generate_qr_code_field()
        self.ref_id_lot_number_expiry_date = (
            self.generate_ref_id_lot_number_expiry_date_field()
        )
        # self.barcode_ref_id_expiry_date = self.generate_barcode_ref_id_expiry_field()
        # self.date_added = self.generate_date_added_field()
        super(Product, self).save(*args, **kwargs)

    def generate_qr_code_field(self):
        formatted_expiry_date = format_date_db_to_qrcode(self.expiry_date)
        return f"{self.name}-{self.barcode}-{formatted_expiry_date}-{self.lot_number}"

    def generate_ref_id_lot_number_expiry_date_field(self):
        return f"{self.reference_id}***{self.lot_number}***{self.expiry_date.date()}"

    # def generate_date_added_field(self):

    #     try:
    #         return self.history.earliest().last_modified
    #     except HistoricalRecords.DoesNotExist:
    #         return adding_tz.localize(datetime.now())

    class Meta:
        unique_together = ("reference_id", "expiry_date", "lot_number")
        # ordering = ["name"]
        ordering = ["expiry_date"]
        indexes = [models.Index(fields=["ref_id_lot_number_expiry_date", "name"])]

    def __str__(self) -> str:
        return self.name

    @property
    def days_until_expiry(self):
        today = date.today()
        # expiry_converted = [int(n) for n in self.expiry_date.split("-")]

        time_remaining = relativedelta(self.expiry_date.date(), today)
        # days_remaining = relativedelta(datetime(*expiry_converted).date(), today)
        # days_remaining = datetime(*expiry_converted).date() - today
        # days_remaining_str = str(days_remaining).split(",", 1)[0]
        return time_remaining


class Procedure(models.Model):
    id = models.BigAutoField(
        auto_created=True,
        primary_key=True,
        unique=True,
        serialize=False,
        verbose_name="procedure_id",)
    procedure = models.CharField(max_length=300, blank=False, null=False)
    patient_mrn = models.PositiveIntegerField(blank=False, null=False, default=0)
    date_performed = models.DateTimeField(auto_now=False, auto_now_add=False)
    products_used = models.ManyToManyField(Product)
    qr_codes_used = models.TextField(blank=False, null=True)
    employee = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    notes = models.JSONField(default=list, blank=True)
    history = HistoricalRecords()

    # CHOICES = [("1", "Add to Inventory"), ("2", "Delete from Inventory")]
    # choice_field = models.CharField(max_length=1, choices=CHOICES)
    class Meta:
        unique_together = ("patient_mrn", "date_performed", "procedure")
        ordering = ["date_performed"]
        indexes = [models.Index(fields=["patient_mrn", "procedure"])]

    def __str__(self) -> str:
        return self.procedure


def jsonfield_default_value():
    return {'update_history': []}


class PO_Item(models.Model):
    id = models.BigAutoField(
        auto_created=True,
        primary_key=True,
        unique=True,
        serialize=False,
        verbose_name="po_item_id",)
    name = models.CharField(max_length=300, default="", blank=False, null=False)
    qty_ordered = models.PositiveIntegerField(default=1, blank=True, null=True)
    qty_received = models.PositiveIntegerField(default=0, blank=True, null=True)
    date_ordered = models.DateTimeField(auto_now=True)
    date_received = models.DateTimeField(auto_now=False, null=True)
    notes = models.JSONField(default=list, blank=True)
    history = HistoricalRecords()

    @property
    def qty_pending(self):
        return self.qty_ordered - self.qty_received


import uuid

def generate_unique_po_number():
    return str(uuid.uuid4())  # Use uuid4 for uniqueness

# default=generate_unique_po_number, # this was for po_number

class PurchaseOrder(models.Model):
    PLACED = "Placed"
    PENDING = "PO Pending/Partially Received"
    COMPLETED = "Completed"

    PO_STATUS_CHOICES = [
        (PLACED, "PO Placed"),
        (PENDING, "PO Pending/Partially Received"),
        (COMPLETED, "PO Completed"),
        ]

    id = models.BigAutoField(
        auto_created=True,
        primary_key=True,
        unique=True,
        serialize=False,
        verbose_name="po_id",)
    po_number = models.CharField(max_length=350, unique=True, null=False) #modify this later to ensure uniqueness
    status = models.CharField(max_length=30, choices=PO_STATUS_CHOICES, default=PLACED, help_text="Select status of PO")
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    po_items = models.ManyToManyField(PO_Item)
    # po_items_list = models.CharField(max_length=300, blank=False, null=True)
    po_date = models.DateTimeField(auto_now=False, null=True)
    employee = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    last_modified = models.DateTimeField(auto_now=False, null=True)
    notes = models.JSONField(default=list, blank=True)
    history = HistoricalRecords(m2m_fields=[po_items])

    def get_po_items(self):
        return "; ".join([f"({str(p.name)}, Quantity {str(p.qty_ordered)} ordered on {self.po_date.strftime('%m-%d-%Y')}, with {str(p.qty_received)} received.) " for p in self.po_items.all()])

    class Meta:
        unique_together = ("po_number", "vendor")
        ordering = ["po_date"]
        indexes = [models.Index(fields=["po_number", "vendor"])]

    def __str__(self) -> str:
        return self.po_number

    def generate_po_number_field(self):
        # adding_tz = pytz.timezone('US/Eastern')
        return f"{self.vendor.abbrev.upper()}-{self.po_date.strftime('%m%d%Y')}-{self.po_date.strftime('%H%M')}"

    def save(self, *args, **kwargs):
        self.vendor.last_ordered = datetime.now(tz=pytz.timezone("US/Eastern"))
        self.vendor.save()
        self.po_number = self.generate_po_number_field()
        super(PurchaseOrder, self).save(*args, **kwargs)


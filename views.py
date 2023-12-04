from django.shortcuts import render, redirect, get_object_or_404
from .models import Product, Vendor, Procedure, PO_Item, PurchaseOrder
from django.contrib.auth.models import User
from django.db.models import Q, Sum
# from django.utils import timezone
# from datetime import datetime
import datetime, pytz
# import json
from .forms import ProductForm, ProcedureForm, VendorForm, PurchaseOrderForm, DateSelectorForm, POItemForm, ProductNotesForm
# from .forms import UneditableProductForm
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse #, HttpResponseNotAllowed
from django.urls import reverse
from django.contrib import messages
from calendar import HTMLCalendar
import calendar
# from django.core import serializers
# from django.views.decorators.cache import cache_control
import traceback
# import qrcode as qr
# import re
from .utils import (get_data_from_api, update_db_from_inventory_csv,
    update_product_in_sheets, construct_search_query, construct_search_query_alternate,
    items_added_30days, items_used_30days, recompose_date, create_procedure_objects_from_sheets_data,
    add_product_to_sheets, create_po_objects_from_sheets_data, sorting_histories)
import threading
import pandas as pd
from dateutil import parser
from django.contrib.auth.decorators import login_required
# import ast


thread_lock = threading.Lock()

@login_required
def all_products(request):
    product_list = Product.objects.all()
    return render(request, "pydb4/product_list.html", {"product_list": product_list})

@login_required
def all_products_used(request):
    product_list = Product.objects.filter(quantity_on_hand=0)
    return render(request, "pydb4/product_list_used.html", {"product_list": product_list})

@login_required
def all_products_expired_still_stocked(request):
    product_list = Product.objects.filter(expiry_date__lte=datetime.datetime.now(), quantity_on_hand__gte=1)
    return render(request, "pydb4/product_list_expired_stocked.html", {"product_list": product_list})


@login_required
def all_vendors(request):
    vendor_list = Vendor.objects.all()
    return render(
        request,
        "pydb4/vendor_list.html",
        {"vendor_list": vendor_list},
    )


@login_required
def database_update_current_inventory(request):
    with thread_lock:
        try:
            data = get_data_from_api(["Current Inventory", True]) # this will gather CSV file
            update_db_from_inventory_csv(data, request.user) # this will pass CSV file to db update function, now along with user
            product_list = Product.objects.all()
            messages.success(request, "Current inventory updated from CSV, please wait 1-2 minutes before new search.")
            return render(
                request,
                "pydb4/product_list.html",
                {"product_list": product_list},
            )
        except Exception as e:
            traceback.print_exc()
            messages.success(request, "Error with updating current inventory, please see stack trace and refer to IT admin.")
            product_list = Product.objects.all()
            return render(
                request,
                "pydb4/product_list.html",
                {"product_list": product_list},
            )

# 11/09/2023: add logic here where request.user also gets passed to procedure update function
@login_required
def database_update_procedures(request):
    with thread_lock:
        try:
            create_procedure_objects_from_sheets_data()
            procedure_list = Procedure.objects.all().order_by('-date_performed')
            messages.success(request, "Current procedures being updated from Google Sheets, please wait 1-2 minutes before new search.")
            return render(
                request,
                "pydb4/procedure_list.html",
                {"procedure_list": procedure_list},
            )
        except Exception:
            traceback.print_exc()
            messages.success(request, "Error with updating current procedures, please see stack trace and refer to IT admin.")
            procedure_list = Procedure.objects.all().order_by('-date_performed')
            return render(
                request,
                "pydb4/procedure_list.html",
                {"procedure_list": procedure_list},
            )
@login_required
def database_update_purchaseorders(request):
    with thread_lock:
        try:
            create_po_objects_from_sheets_data(request.user.id)
            po_list = PurchaseOrder.objects.all().order_by('-po_date')
            messages.success(request, "Current POs being updated from Google Sheets, please wait 1-2 minutes before new search.")
            return render(
                request,
                "pydb4/po_list.html",
                {"po_list": po_list},
            )
        except Exception:
            traceback.print_exc()
            messages.success(request, "Error with updating current POs, please see stack trace and refer to IT admin.")
            po_list = PurchaseOrder.objects.all().order_by('-po_date')
            return render(
                request,
                "pydb4/po_list.html",
                {"po_list": po_list},
            )



@login_required
def all_procedures(request):
    # insert function call to update procedures based on items used sheet, see utils
    procedure_list = Procedure.objects.all().order_by('-date_performed')
    oldest = Procedure.objects.all().order_by('date_performed').first()
    return render(
        request,
        "pydb4/procedure_list.html",
        {"procedure_list": procedure_list, 'oldest': oldest},
    )

@login_required
def all_purchase_orders(request):
    # insert function call to update procedures based on items used sheet, see utils
    po_list = PurchaseOrder.objects.all().order_by('-po_date')
    return render(
        request,
        "pydb4/po_list.html",
        {"po_list": po_list},
    )

@login_required
def all_vendor_products(request, vendor_id):
    print('all_vendor_products view: ', request.META.get('HTTP_X_REQUESTED_WITH'))
    if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        products = Product.objects.filter(vendor_id=vendor_id)
        vendor = Vendor.objects.get(id=vendor_id)
        product_data = [{"name": p.name} for p in products]
        vendor_data = {
            'id': vendor.id,
            'name': vendor.name,
            # Can add any other desired fields
        }
        response_data = {
            'products': product_data,
            'vendor': vendor_data,
        }
        # response_json = json.dumps(response_data)
        return JsonResponse(response_data, safe=False)
    else:
        products = Product.objects.filter(vendor_id=vendor_id)
        vendor = Vendor.objects.get(id=vendor_id)
        return render(
            request,
            "pydb4/vendor_products.html",
            {"products": products, "vendor": vendor},
        )

@login_required
def expiry_check_custom_dates(request):
    submitted = False
    if request.method == "POST":
        print(request.POST)
        print('test_widgets: ', request.POST.items())
        start = request.POST['date_start']
        end = request.POST['date_end']
        # can add, if start == end logic, so as to say, if less/than/equalto (lte) today, all in range from today till that point)
        products = Product.objects.filter(expiry_date__range=(recompose_date(start, return_str=False), recompose_date(end, return_str=False)))
        submitted = True
        # messages.success(request, f"Search results starting from {start} until {end}.", extra_tags='search')
        start_ref = recompose_date(start, db_format=False)
        end_ref = recompose_date(end, db_format=False)
        return render(request, "pydb4/expiring_products_list.html", {"product_list": products, 'submitted':submitted, 'start': start_ref, 'end': end_ref})
    form = DateSelectorForm()
    return render(request, 'pydb4/expiry_check_custom.html', {'form':form, 'submitted':submitted})

@login_required
def product_detail(request, item_id):
    product = Product.objects.get(id=item_id)
    records = sorting_histories(product)
    return render(request, "pydb4/product_detail.html", {"product": product, "records": records})

@login_required
def procedure_detail(request, procedure_id):
    procedure = Procedure.objects.get(id=procedure_id)
    products = procedure.products_used.all()
    # --- later can add reference below to context dict, such as details of procedure (who entered it etc)
    # records = AuditLog.objects.filter(Q(object_id=item_id) & Q(field_name="quantity_on_hand")).order_by('-modified_date')
    # for r in records:
    #     print(r.content_object)
    #     print(r.object_id)
    #     print(r.field_name)
    return render(request, "pydb4/procedure_detail.html", {"procedure": procedure, "products": products})

@login_required
def po_detail(request, po_id):
    purchase_order = PurchaseOrder.objects.get(id=po_id)
    po_items = purchase_order.po_items.all()
    return render(request, "pydb4/po_detail.html", {"po": purchase_order, 'po_items': po_items})

@login_required
def product_search(request):
    multiple = ''
    if request.method == "POST":
        searched = request.POST["searched"].strip().lower()
        if request.POST.get("search_option") == 'barcode' or request.POST.get("search_option") == 'single':
            # products = [s.strip().lower() for s in searched.split("-") if '-' in search else ]
            if '-' in searched and searched.count('-') == 3:
                multiple = 'barcode'
                product = [s.strip() for s in searched.split("-")]
                queries = (
                    Q(name__icontains=product[0])
                    & Q(barcode__icontains=product[1])
                    & Q(expiry_date__exact=recompose_date(phrase=product[2], return_str=False))
                    & Q(lot_number__icontains=product[3])
                )
                search_query = queries
            else:
                multiple = 'single'
                product = [s.strip() for s in searched.split(" ")]
                # recompose_date(phrase=term, return_str=False)
                # db_date_format_alt(term)
                queries = [
                    Q(name__icontains=term)
                    # | Q(size__icontains=term)
                    | Q(barcode__icontains=term)
                    | Q(reference_id__icontains=term)
                    | Q(lot_number__icontains=term)
                    # | Q(expiry_date__exact=recompose_date(phrase=term, return_str=False))
                    for term in product
                ]
                print(queries)
                search_query = construct_search_query_alternate(queries)
            result = Product.objects.filter(search_query).order_by('expiry_date')
            total_quantity_results = result.aggregate(Sum("quantity_on_hand"))
            return render(request, "pydb4/product_search.html", {"searched": product, "products": result, "multiple": multiple, "total_num": total_quantity_results['quantity_on_hand__sum']})
        elif request.POST.get("search_option") == 'multiple':
            multiple = 'multiple'
            products = [s.strip().lower() for s in searched.split(" ")]
            queries = [
                Q(name__icontains=term)
                # | Q(size__icontains=term)
                | Q(reference_id__icontains=term)
                | Q(barcode__icontains=term)
                | Q(lot_number__icontains=term)
                # | Q(expiry_date__exact=recompose_date(phrase=term, return_str=False))
                for term in products
            ]
            search_query = construct_search_query(queries)
            results = Product.objects.filter(search_query).order_by('expiry_date')
            total_quantity_results = results.aggregate(Sum("quantity_on_hand"))
            return render(request, "pydb4/product_search.html", {"searched": products, "products": results, "multiple": multiple, "total_num": total_quantity_results['quantity_on_hand__sum']})
        else:
            products = Product.objects.filter(
                Q(name__icontains=searched)
                # | Q(size__icontains=searched)
                | Q(reference_id__icontains=searched)
                | Q(barcode__icontains=searched)
                | Q(lot_number__icontains=searched)
                # | Q(expiry_date__exact=recompose_date(phrase=searched, return_str=False))
            ).order_by("expiry_date")
            total_quantity_results = products.aggregate(Sum("quantity_on_hand"))
            messages.success(request, "Search completed!", extra_tags='search')
            return render(
                request,
                "pydb4/product_search.html",
                {
                    "searched": searched,
                    "products": products,
                    "multiple": multiple,
                    "total_num": total_quantity_results['quantity_on_hand__sum']
                },
            )
    else:
        return render(request, "pydb4/product_list.html", {})

@login_required
def update_product(request, product_id):
    product = Product.objects.get(pk=product_id)
    print('product instance info: ', product.last_modified, product.quantity_on_hand)
    if not product.last_modified:
        product.last_modified = datetime.datetime(1900, 1, 1)
    updated = False
    readonly_fields = ['name', 'reference_id', 'size', 'expiry_date', 'vendor']
    # readonly_fields = ['name', 'reference_id', 'expiry_date', 'vendor']
    if request.method == "POST":
        print('dict and items here:', list(request.POST.items()))
        print('POST form instance info: ', request.POST.get('last_modified'), request.POST.get('quantity_on_hand'))
        form = ProductForm(request.POST, instance=product, readonly_fields=readonly_fields)
        # for field in readonly_fields:
        #     form.fields[field].initial = getattr(product, field)
        #     form.fields[field].widget.attrs['readonly'] = True
        if form.is_valid():
            result = form.save(commit=False)
            try:
                result.employee = User.objects.get(pk=request.user.id) #logged in user
            except Exception:
                traceback.print_exc()
            print(f'For updating {product.name}, User ID: {request.user.id}')
            update_product_in_sheets(result.quantity_on_hand, result.reference_id, result.lot_number, result.expiry_date)
            now = datetime.datetime.now(tz=pytz.timezone("US/Eastern"))
            if product.quantity_on_hand != request.POST.get('quantity_on_hand') or product.is_purchased != request.POST.get('is_purchased'):
                result.last_modified = now
            else:
                result.last_modified = product.last_modified
            result.save()
            updated = True
            redirect_url = reverse('product_detail', args=[product_id])
            if updated:
                redirect_url += '?redirect_flag=true'
            print(result.employee.username)
            redirect_url += f'?user={result.employee.username}'
            return HttpResponseRedirect(redirect_url)
        else:
            print(form.errors)
            messages.error(request, f"Form unable to be saved, please contact IT admin. {form.errors}")
    else:
        form = ProductForm(instance=product, readonly_fields=readonly_fields)
    return render(request, 'pydb4/update_product.html', {"product": product, "form": form, "readonly_fields": readonly_fields})

@login_required
def update_po(request, po_id):
    from django.forms import modelformset_factory
    po = PurchaseOrder.objects.get(pk=po_id)
    POItemFormSet = modelformset_factory(PO_Item, form=POItemForm, extra=0)
    print('purchase order instance info: ', po.last_modified, len(po.po_items.all()))
    updated = False
    readonly_fields = ['vendor', 'po_date']
    # readonly_fields = ['name', 'reference_id', 'expiry_date', 'vendor']
    print('dict and items here:', request.POST.items())
    if request.method == "POST":
        form = PurchaseOrderForm(request.POST, instance=po, readonly_fields=readonly_fields)
        po_item_formset = POItemFormSet(request.POST, queryset=po.po_items.all())
        print('this is dict of form:', list(form))
        print('this is dict of formset:', list(po_item_formset))
        # form.status = po.status
        # for field in readonly_fields:
        #     form.fields[field].initial = getattr(product, field)
        #     form.fields[field].widget.attrs['readonly'] = True
        print(dict(request.POST))
        print(form.is_valid(), ' is form.is_valid(), this is po item formset valid boolean: ', po_item_formset.is_valid())
        if form.is_valid():
            result_po = form.save(commit=False)
            if po_item_formset.is_valid():
                result_po_item_formset = po_item_formset.save()
            else:
                print(po_item_formset.errors)
                print(po_item_formset)
            # for po_item_form in po_item_formset:
            #     print('po item form valid? for', po_item_form)
            #     if po_item_form.is_valid():
            #         print('po item form IS valid for', po_item_form)
            #         po_item_form.save()
            try:
                result_po.employee = User.objects.get(pk=request.user.id) #logged in user
            except Exception:
                traceback.print_exc()
            now = datetime.datetime.now(tz=pytz.timezone("US/Eastern"))
            result_po.last_modified = now
            result_po.save()
            po_item_formset.save()
            po_updated = PurchaseOrder.objects.get(id=result_po.id)
            for item in po_updated.po_items.all():
                item.notes += [((len(item.notes)+1), now.strftime("%m-%d-%Y"))]
                item.save()
            updated = True
            redirect_url = reverse('po_detail', args=[po_id])
            if updated:
                redirect_url += '?redirect_flag=true'
            print(result_po.employee.username)
            redirect_url += f'?user={result_po.employee.username}'
            return HttpResponseRedirect(redirect_url)
        else:
            print(form.errors)
            messages.error(request, f"{po_item_formset.errors}Form unable to be saved, please contact IT admin. {po_item_formset.errors}\n---{form.is_valid()}\n -- poitemformset{po_item_formset.is_valid()}--{form.status}----{form.non_field_errors}")
    else:
        form = PurchaseOrderForm(instance=po, po_id=po_id)
        po_item_formset = POItemFormSet(queryset=po.po_items.all())
    return render(request, 'pydb4/update_po.html', {"po": po, "form": form, "po_item_formset": po_item_formset, "readonly_fields": readonly_fields})



@login_required
def report_items_added_30days(request):
    data_df = get_data_from_api(["New Items for Inventory FORM", False]) # this gathers df of items new
    data_df_processed = items_added_30days(data_df)
    items_dict = data_df_processed.to_dict(orient="records")
    # above is a list of dict objects that represent data from sheets file reflecting items added last 30 days,
    # can also check this versus database, match items, and then pass those products (as QuerySet dict) to context object
    # ---- add this line to reports-items-added html template, to get link for each item, once their records match
    #         <strong><a href="{% url 'product_detail' p.id %}">{{p.name}}</a></strong>
    # so that it could be easier to define properly in the html template
    # for item in items_dict:
    #     check = Product.objects.filter(ref_id_lot_number_expiry_date__icontains=item['ref_id_lot_number_expiry_date'])
    #     if check.exists():
    #         item['id'] = check.first().id
    #         print('added ID for this item to items_dict:', item['name'])
    product_list = items_dict
    return render(request, "pydb4/products_added_30days_report.html", {"product_list": product_list})

@login_required
# mirror of above, if comments needed
def report_items_used_30days(request):
    data_df = get_data_from_api(["Items Used in Procedure FORM", False]) # this gathers df of items used
    data_df_processed = items_used_30days(data_df)
    # list of attributes to add as columns, these are absent from the items used sheet
    attributes_to_add = ['name', 'reference_id', 'id', 'expiry_date', 'quantity_on_hand', 'vendor', 'size', 'lot_number']
    barcode_list = data_df_processed["barcode"]
    # dictionary to collect attribute data for each barcode
    data_dict = {}
    for barcode in barcode_list:
        barcode = str(barcode).strip()
        objs = Product.objects.filter(Q(barcode__icontains=barcode) | Q(qr_code__icontains=barcode))
        # list to store attribute data for each object
        objs_data = []
        for obj in objs:
            # dictionary to store attribute data for this object
            obj_data = {}
            # Collect attribute values for this object
            for attribute in attributes_to_add:
                obj_data[attribute] = getattr(obj, attribute)
            # Add the collected data for this object to the list
            objs_data.append(obj_data)
        # Add the list of attribute data for this barcode to the main data dictionary
        data_dict[barcode] = objs_data
    # Now, data_dict holds lists of attribute data for each barcode (can flatten or keep nested)
    # Flattening the data for each barcode into a single dictionary
    flattened_data_dict = {}
    for barcode, objs_data in data_dict.items():
        # Merge the dictionaries for each object into a single dictionary
        flattened_data_dict[barcode] = {k: v for obj_data in objs_data for k, v in obj_data.items()}
    # Convert the flattened data dictionary into a DataFrame
    print(flattened_data_dict, 'line 320 in items used report')
    additional_data_df = pd.DataFrame.from_dict(flattened_data_dict, orient='index')
    print('this is additional data df:')
    print(additional_data_df)
    data_df_processed = data_df_processed.merge(additional_data_df, left_on='barcode', right_index=True)
    items_dict = data_df_processed.to_dict(orient="records")
    product_list = items_dict
    return render(request, "pydb4/products_used_30days_report.html", {"product_list": product_list})

@login_required
def expiry_check_products_by_month(request, month_number):
    now = datetime.datetime.now(tz=pytz.timezone("US/Eastern"))
    products = Product.objects.filter(quantity_on_hand__gt=0).filter(expiry_date__gt=now)
    results = []
    for x in products:
        datecheck = x.days_until_expiry
        if month_number == 1:
            if datecheck.years == 0 and datecheck.months <= 1:
                print(x.name, x.size, x.expiry_date.date())
                results.append(x)
        if month_number == 3:
            if datecheck.years == 0 and datecheck.months <= 3 and datecheck.months > 1:
                print(x.name, x.size, x.expiry_date.date())
                results.append(x)
        if month_number == 6:
            if datecheck.years == 0 and datecheck.months <= 6 and datecheck.months > 3:
                print(x.name, x.size, x.expiry_date.date())
                results.append(x)
    return render(request, 'pydb4/expiry_check.html', {"results": results, "month_number": month_number})

@login_required
# def verify_products(request):
#     submitted = False
#     if request.method == "POST":
#         print('got to here, line 201 in views.py')
#         pattern = r"\r\n|\n|,"  # Regular expression pattern to match "\r\n" or "\n"
#         barcodes_used = re.split(pattern, request.POST.get('products_used', ''))
#         queries = [Q(barcode__icontains=term) for term in barcodes_used if term != '']
#         search_query = construct_search_query(queries)
#         results = Product.objects.filter(search_query).order_by('expiry_date')

#     print('got to here, line 209 in views.py')
#     return HttpResponseNotAllowed(['POST'])

@login_required
def extract_objects_using_qr_code(qr_codes_used):
    queries = []
    # Construct individual Q objects for each term
    for term in qr_codes_used:
        date_obj = parser.parse(term.split('-')[2]).date()
        # Construct your Q objects for this term
        q_obj = Q(qr_code__icontains=term) | (Q(expiry_date=date_obj) & Q(name__icontains=term.split('-')[0]) & Q(barcode__icontains=term.split('-')[1]))
        queries.append(q_obj)
    # Combine all the Q objects using logical OR
    search_query = Q()
    for query in queries:
        search_query |= query
    # Query the database
    results = Product.objects.filter(search_query).order_by('expiry_date')
    return results

@login_required
def procedure(request):
    submitted = False
    if request.method == "POST":
        print("POST here")
        form = ProcedureForm(request.POST)
        qr_codes_used = [s.strip() for s in request.POST.get('qr_codes_used').split("&") if s not in ['', None]]
        queries = []
        # Construct individual Q objects for each term
        for term in qr_codes_used:
            date_obj = parser.parse(term.split('-')[2]).date()
            # this is looking either for precise qr_code match OR all matches for expiry+name+barcode together in one item
            q_obj = Q(qr_code__icontains=term) | (Q(expiry_date=date_obj) & Q(name__icontains=term.split('-')[0]) & Q(barcode__icontains=term.split('-')[1]))
            queries.append(q_obj)
        # Combine all the Q objects using logical OR
        search_query = Q()
        for query in queries:
            search_query |= query
        results = Product.objects.filter(search_query).order_by('expiry_date')
        if results.first() is None:
            form = ProcedureForm()
            messages.success(request, "Incorrect data entered for products used, please submit procedure with corrected information.")
            return render(request, 'pydb4/procedure_event.html', {'form': form, 'submitted': submitted})
        # print('length of results queryset:')
        print('len of results',len(results))
        print(results)
        print('.items: ', request.POST.items)
        # print('original products used field: ', qr_codes_used)
        # print('processed products used field', products_used)
        print('patient_mrn: ', request.POST.get('patient_mrn'))
        print('procedure: ', request.POST.get('procedure'))
        if form.is_valid():
            print(type(form),'the form is valid\n:', form)
            procedure = form.save(commit=False)
            try:
                print('For adding procedure, User ID: ', request.user.id)
                procedure.employee = User.objects.get(pk=request.user.id) #logged in user
                procedure.qr_codes_used = qr_codes_used
                if results:
                    print('showing len, type, and results object itself:')
                    print(len(results), type(results), results)
                    for r in results:
                        print(f"Removing one of this item from inventory: {r.name}-{r.expiry_date}")
                        print(f"Old quant: {r.quantity_on_hand}")
                        # r.quantity_on_hand -= 1
                        # ---- uncomment above when ready to have add procedure to remove an item from inventory ---
                        # print(f"New quant: {r.quantity_on_hand} ---temporarily disabled, see views.procedure")
                        # r.save()
                        print(f'added {r} to Procedure object, then to be saved')
                procedure.save()
                procedure.products_used.add(*results)
                # for r in results:
                #     procedure.products_used.add(r) # changed to ManyToMany field in model of Procedure
            except:
                traceback.print_exc()
            submitted = True
            return render(request, 'pydb4/procedure_detail.html', {'procedure': procedure, 'submitted': submitted, 'products': results})
        else:
            # print(form.is_valid()) # returns boolean
            print(form.errors)
            print('sorry form not correct, try again.')
            form = ProcedureForm()
            return render(request, 'pydb4/procedure_event.html', {'form': form, 'submitted': submitted})
    else:
        form = ProcedureForm()
        print('GET here')
        return render(request, 'pydb4/procedure_event.html', {'form': form, 'submitted': submitted})

@login_required
def create_po(request):
    submitted = False
    if request.method == "POST":
        from collections import Counter
        form = PurchaseOrderForm(request.POST)
        print('full request post dict: ', request.POST)
        # print('patient_mrn: ', request.POST.get('patient_mrn'))
        # print('procedure: ', request.POST.get('procedure'))
        extracted_dict = {k:v for k, v in request.POST.items() if 'po_item_' in k}
        # print('extracted_dict here: ', extracted_dict)
        key_count_dict = dict(Counter(x[-1:] for x in extracted_dict.keys() if x and extracted_dict[x] != ''))
        po_item_valid_objects = {k:v for k, v in extracted_dict.items() for x, y in key_count_dict.items() if x in k and y == 2}
        paired_po_items = [
            (x, y)
            for i_x, x in enumerate(po_item_valid_objects.values())
            for i_y, y in enumerate(po_item_valid_objects.values())
            if i_y == 1 + i_x and i_x % 2 == 0
        ]
        if form.is_valid():
            purchase_order = form.save(commit=False)
            # item_formset.save()
            try:
                print('For creating new PO, User ID: ', request.user.id)
                purchase_order.employee = User.objects.get(pk=request.user.id) #logged in user
                purchase_order.save()
                for po_item in paired_po_items:
                    item = PO_Item(name=po_item[0], qty_ordered=po_item[1])
                    item.save()
                    purchase_order.po_items.add(item)
            except:
                traceback.print_exc()
            submitted = True
            messages.success(request, "Purchase order created successfully.")
            return render(request, "pydb4/create_po.html", {"form": purchase_order, 'submitted': submitted})
        else:
            print(form.errors)
            print('sorry form not correct, try again.')
            messages.success(request, "Purchase order form not correct, please try again...")
            form = PurchaseOrderForm()
            return render(request, "pydb4/create_po.html", {"form": purchase_order, 'submitted': submitted})
    form = PurchaseOrderForm()
    return render(request, 'pydb4/create_po.html', {'form':form, 'submitted':submitted})


@login_required
def add_product(request):
    submitted = False
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            # venue = form.save(commit=False)
            # venue.owner = request.user.id # logged in user
            # venue.save()
            product = form.save(commit=False)
            try:
                print('For adding product, User ID: ', request.user.id)
                product.employee = User.objects.get(pk=request.user.id) #logged in user
                # product.employee = request.user.id
                now = datetime.datetime.now(tz=pytz.timezone("US/Eastern"))
                product.last_modified = now
                product.save()
                add_product_to_sheets(quantity=product.quantity_on_hand, vendor=product.vendor.name, product_name=product.name, product_size=product.size, expiry_date=recompose_date(product.expiry_date, db_format=False), reference_id=product.reference_id, lot_number=product.lot_number, barcode=product.barcode)
            except:
                traceback.print_exc()
            submitted = True
            messages.success(request, "Product added successfully.")
            # return  render('/add_product?submitted=True')
            print(type(product))
            return render(request, "pydb4/product_detail.html", {"product": product, 'submitted': submitted})
    else:
        form = ProductForm()
        if 'submitted' in request.GET:
            submitted = True
        return render(request, 'pydb4/add_product.html', {'form':form, 'submitted':submitted})

@login_required
def add_vendor(request):
    submitted = False
    if request.method == "POST":
        form = VendorForm(request.POST)
        vendors = Vendor.objects.filter(id=request.POST.get("id"), name=request.POST.get("name"), abbrev=request.POST.get("abbrev"))
        if not vendors.exists():
            if form.is_valid():
                try:
                    vendor = form.save(commit=False)
                    print('Adding new vendor, Vendor ID: ', vendor.id)
                    vendor.employee = User.objects.get(pk=request.user.id)  # logged in user
                    vendor.save()
                    messages.success(request, "Vendor added successfully.")
                    submitted = True
                    products = Product.objects.filter(vendor_id=vendor.id)
                    return render(request, "pydb4/vendor_products.html", {"vendor": vendor, 'submitted': submitted, 'products': products})
                except Exception as e:
                    traceback.print_exc()
                    print('An error occurred:', str(e))
                    return HttpResponse("An error occurred while adding the vendor. Please try again later.")
            else:
                # Handle form validation errors here
                print('Form errors here:', form.errors)
                messages.success(request, "Form validation failed. Please check the data you entered: \n All Vendor information must be unique (ID, Name, Abbreviation).")
                vendor_list = Vendor.objects.all()
                return render(
                    request,
                    "pydb4/vendor_list.html",
                    {"vendor_list": vendor_list},
                )
        else:
            vendor = vendors.first()
            messages.success(request, "Vendor already exists in records.")
            products = Product.objects.filter(vendor_id=vendor.id)
            return HttpResponseRedirect(reverse('all-vendor-products', args=[vendor.id]))  # Redirect to vendor detail page
    else:
        form = VendorForm()
        if 'submitted' in request.GET:
            submitted = True
        return render(request, 'pydb4/add_vendor.html', {'form': form, 'submitted': submitted})


def home(request, year=datetime.datetime.now().year, month=datetime.datetime.now().strftime('%B')):
    name = "Guest"
    month = month.capitalize()
    # Convert month from name to number
    month_number = list(calendar.month_name).index(month)
    month_number = int(month_number)
    # create a calendar
    cal = HTMLCalendar().formatmonth(
        year,
        month_number)
    # Get current year
    # now = datetime.now()
    now = datetime.datetime.now(tz=pytz.timezone("US/Eastern"))
    current_year = now.year
    current_day = now.day
    # Query the Events Model For Dates
    # event_list = Event.objects.filter(
    #     event_date__year = year,
    #     event_date__month = month_number
    #     )
    # Get current time
    time = now.strftime('%I:%M %p')
    return render(request,
        'pydb4/home.html', {
        "name": name,
        "year": year,
        "month": month,
        "month_number": month_number,
        "cal": cal,
        "current_day": current_day,
        "current_year": current_year,
        "time":time,
        # "event_list": event_list,
        })

*----------------------------------------------------------------------*
* ABAP Dictionary Definitions - Sample schema definitions
* Demonstrates TYPES, DATA, CDS views, and table types
*----------------------------------------------------------------------*

REPORT z_schema_demo.

*----------------------------------------------------------------------*
* Type definitions for User entity
*----------------------------------------------------------------------*
TYPES: BEGIN OF ty_user,
         mandt    TYPE mandt,
         user_id  TYPE char10,
         username TYPE char40,
         email    TYPE char100,
         dept_id  TYPE char10,
         created  TYPE timestamp,
       END OF ty_user.

* Table type for user list
TYPES: tt_user TYPE STANDARD TABLE OF ty_user WITH DEFAULT KEY.

*----------------------------------------------------------------------*
* Type definitions for Order entity (with foreign keys)
*----------------------------------------------------------------------*
TYPES: BEGIN OF ty_order,
         order_id    TYPE vbeln,       " Sales doc number - FK to sales_documents
         customer_id TYPE kunnr,       " Customer number - FK to customers
         material    TYPE matnr,       " Material number - FK to materials
         quantity    TYPE int4,
         amount      TYPE p LENGTH 8 DECIMALS 2,
         currency    TYPE waers,
         status      TYPE char1,
         created_at  TYPE timestamp,
       END OF ty_order.

TYPES: tt_orders TYPE STANDARD TABLE OF ty_order WITH DEFAULT KEY.

*----------------------------------------------------------------------*
* Data declaration for Product structure
*----------------------------------------------------------------------*
DATA: BEGIN OF gs_product,
        product_id  TYPE char10,
        name        TYPE char80,
        description TYPE string,
        price       TYPE p DECIMALS 2,
        category    TYPE char20,
        vendor_id   TYPE lifnr,       " Vendor number - FK to vendors
        plant       TYPE werks,       " Plant - FK to plants
        created_at  TYPE dats,
        updated_at  TYPE tims,
      END OF gs_product.

* Table declaration
DATA: gt_products TYPE STANDARD TABLE OF gs_product.

*----------------------------------------------------------------------*
* Include structure
*----------------------------------------------------------------------*
INCLUDE TYPE zcustomer_data.

*----------------------------------------------------------------------*
* Constants for table names
*----------------------------------------------------------------------*
CONSTANTS: gc_table_users TYPE tabname VALUE 'ZUSER_MASTER'.
CONSTANTS: gc_table_orders TYPE tabname VALUE 'ZORDER_HEADER'.

*----------------------------------------------------------------------*
* Type with NUMC and DEC fields
*----------------------------------------------------------------------*
TYPES: BEGIN OF ty_accounting,
         doc_number  TYPE belnr,       " Accounting doc - FK to accounting_docs
         company     TYPE bukrs,       " Company code - FK to company_codes
         fiscal_year TYPE gjahr,       " Fiscal year
         amount      TYPE dec DECIMALS 2,
         tax_amount  TYPE curr DECIMALS 2,
         posting_date TYPE dats,
         entry_time   TYPE tims,
       END OF ty_accounting.

*----------------------------------------------------------------------*
* CDS View Definition
*----------------------------------------------------------------------*
@AbapCatalog.sqlViewName: 'ZUSER_V'
@EndUserText.label: 'User Master View'
define view ZI_User as select from zuser_master {
  key user_id,
      username,
      email,
      dept_id
}

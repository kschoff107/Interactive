*----------------------------------------------------------------------*
* ABAP Runtime Flow Sample
* Demonstrates FORM, CLASS/METHOD, CALL FUNCTION, control flow
*----------------------------------------------------------------------*

REPORT z_flow_demo.

*----------------------------------------------------------------------*
* Event blocks (entry points)
*----------------------------------------------------------------------*
INITIALIZATION.
  DATA: gv_initialized TYPE abap_bool.
  gv_initialized = abap_true.

START-OF-SELECTION.
  DATA: lv_amount TYPE p DECIMALS 2 VALUE '100.00'.
  DATA: lv_total  TYPE p DECIMALS 2.

  PERFORM calculate_total USING lv_amount CHANGING lv_total.
  WRITE: / 'Total:', lv_total.

AT SELECTION-SCREEN.
  " Validate user input
  IF sy-ucomm = 'ONLI'.
    PERFORM validate_input.
  ENDIF.

*----------------------------------------------------------------------*
* Subroutine: calculate_total
*----------------------------------------------------------------------*
FORM calculate_total USING iv_amount TYPE p
                     CHANGING cv_total TYPE p.
  DATA: lv_tax TYPE p DECIMALS 2.
  lv_tax = iv_amount * '0.1'.
  cv_total = iv_amount + lv_tax.

  IF cv_total > 1000.
    PERFORM apply_discount CHANGING cv_total.
  ENDIF.

  CALL FUNCTION 'CONVERSION_EXIT_ALPHA_INPUT'
    EXPORTING
      input  = cv_total
    IMPORTING
      output = cv_total.
ENDFORM.

*----------------------------------------------------------------------*
* Subroutine: apply_discount
*----------------------------------------------------------------------*
FORM apply_discount CHANGING cv_total TYPE p.
  cv_total = cv_total * '0.95'.

  DO 3 TIMES.
    cv_total = cv_total - 1.
  ENDDO.

  WHILE cv_total > 5000.
    cv_total = cv_total * '0.99'.
  ENDWHILE.
ENDFORM.

*----------------------------------------------------------------------*
* Subroutine: validate_input
*----------------------------------------------------------------------*
FORM validate_input.
  DATA: lv_valid TYPE abap_bool.

  CASE sy-ucomm.
    WHEN 'ONLI'.
      lv_valid = abap_true.
    WHEN 'BACK'.
      lv_valid = abap_false.
    WHEN OTHERS.
      lv_valid = abap_false.
  ENDCASE.

  IF lv_valid = abap_false.
    MESSAGE e001(zmsg_class).
  ENDIF.
ENDFORM.

*----------------------------------------------------------------------*
* Class definition
*----------------------------------------------------------------------*
CLASS zcl_order_processor DEFINITION.
  PUBLIC SECTION.
    METHODS: process_order IMPORTING iv_order_id TYPE vbeln
                           RETURNING VALUE(rv_success) TYPE abap_bool,
             validate_order IMPORTING iv_order_id TYPE vbeln
                            RETURNING VALUE(rv_valid) TYPE abap_bool.

  PRIVATE SECTION.
    METHODS: log_processing IMPORTING iv_order_id TYPE vbeln
                                      iv_status   TYPE char1.
ENDCLASS.

*----------------------------------------------------------------------*
* Class implementation
*----------------------------------------------------------------------*
CLASS zcl_order_processor IMPLEMENTATION.
  METHOD process_order.
    DATA(lv_valid) = validate_order( iv_order_id ).

    IF lv_valid = abap_true.
      CALL FUNCTION 'BAPI_ORDER_CONFIRM'
        EXPORTING
          order_id = iv_order_id.

      TRY.
          CALL METHOD me->log_processing
            EXPORTING
              iv_order_id = iv_order_id
              iv_status   = 'S'.
          rv_success = abap_true.
        CATCH cx_sy_open_sql_db.
          rv_success = abap_false.
      ENDTRY.
    ELSE.
      rv_success = abap_false.
    ENDIF.
  ENDMETHOD.

  METHOD validate_order.
    SELECT SINGLE * FROM vbak WHERE vbeln = @iv_order_id INTO @DATA(ls_order).
    rv_valid = COND #( WHEN sy-subrc = 0 THEN abap_true ELSE abap_false ).

    IF rv_valid = abap_true.
      LOOP AT ls_order-items INTO DATA(ls_item).
        IF ls_item-quantity <= 0.
          rv_valid = abap_false.
          EXIT.
        ENDIF.
      ENDLOOP.
    ENDIF.
  ENDMETHOD.

  METHOD log_processing.
    CALL FUNCTION 'Z_LOG_ENTRY'
      EXPORTING
        object_id = iv_order_id
        status    = iv_status.
  ENDMETHOD.
ENDCLASS.

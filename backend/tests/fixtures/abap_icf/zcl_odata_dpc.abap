*----------------------------------------------------------------------*
* OData Data Provider Class for User entity
* Implements standard CRUD operations
*----------------------------------------------------------------------*

CLASS zcl_user_dpc_ext DEFINITION
  INHERITING FROM zcl_user_dpc.

  PUBLIC SECTION.

  PROTECTED SECTION.
    METHODS: /iwbep/if_mgw_appl_srv_runtime~get_entityset REDEFINITION,
             /iwbep/if_mgw_appl_srv_runtime~get_entity REDEFINITION,
             /iwbep/if_mgw_appl_srv_runtime~create_entity REDEFINITION,
             /iwbep/if_mgw_appl_srv_runtime~update_entity REDEFINITION,
             /iwbep/if_mgw_appl_srv_runtime~delete_entity REDEFINITION.

  PRIVATE SECTION.
    METHODS: map_to_entity IMPORTING is_data TYPE zuser_data
                           RETURNING VALUE(rs_entity) TYPE zcl_user_mpc=>ts_user.
ENDCLASS.

CLASS zcl_user_dpc_ext IMPLEMENTATION.
  METHOD /iwbep/if_mgw_appl_srv_runtime~get_entityset.
    DATA: lt_users TYPE TABLE OF zuser_data.
    SELECT * FROM zuser_master INTO TABLE lt_users.
    " Map internal table to entity set
  ENDMETHOD.

  METHOD /iwbep/if_mgw_appl_srv_runtime~get_entity.
    DATA: ls_user TYPE zuser_data.
    " Read single user by key
    SELECT SINGLE * FROM zuser_master INTO ls_user
      WHERE user_id = iv_key.
  ENDMETHOD.

  METHOD /iwbep/if_mgw_appl_srv_runtime~create_entity.
    " Create new user record
    DATA: ls_user TYPE zuser_data.
    io_data_provider->read_entry_data( IMPORTING es_data = ls_user ).
    INSERT zuser_master FROM ls_user.
  ENDMETHOD.

  METHOD /iwbep/if_mgw_appl_srv_runtime~update_entity.
    " Update existing user
    DATA: ls_user TYPE zuser_data.
    io_data_provider->read_entry_data( IMPORTING es_data = ls_user ).
    MODIFY zuser_master FROM ls_user.
  ENDMETHOD.

  METHOD /iwbep/if_mgw_appl_srv_runtime~delete_entity.
    " Delete user by key
    DELETE FROM zuser_master WHERE user_id = iv_key.
  ENDMETHOD.

  METHOD map_to_entity.
    MOVE-CORRESPONDING is_data TO rs_entity.
  ENDMETHOD.
ENDCLASS.

*----------------------------------------------------------------------*
* RAP Behavior Definition
*----------------------------------------------------------------------*
@EndUserText.label: 'Order Service'
define behavior for ZI_Order alias Order
{
  create;
  update;
  delete;

  association _Items { create; }

  action confirmOrder result [1] $self;
}

*----------------------------------------------------------------------*
* ICF HTTP Handler
*----------------------------------------------------------------------*
CLASS zcl_http_handler DEFINITION
  INHERITING FROM cl_rest_http_handler.

  PROTECTED SECTION.
    METHODS: get_root_handler REDEFINITION.

  PRIVATE SECTION.
    METHODS: handle_get FOR TESTING,
             handle_post FOR TESTING.
ENDCLASS.

CLASS zcl_http_handler IMPLEMENTATION.
  METHOD get_root_handler.
    " Return REST resource handler
  ENDMETHOD.

  METHOD handle_get.
    " Process GET requests
  ENDMETHOD.

  METHOD handle_post.
    " Process POST requests
  ENDMETHOD.
ENDCLASS.

"""Workflow templates for quick setup."""

from __future__ import annotations

CRUD_BASIC_TEMPLATE = '''# Basic CRUD Workflow Template
workflows:
  - name: resource_crud
    description: "Basic CRUD operations for a resource"
    tags:
      - crud
      - smoke
    
    variables:
      resource_name: "Test Resource"
    
    steps:
      - name: create_resource
        endpoint: POST /resources
        description: "Create a new resource"
        request:
          body:
            name: "${resource_name}"
            description: "Created by workflow test"
        expect:
          status: [201]
        extract:
          resource_id: $.id
      
      - name: get_resource
        endpoint: GET /resources/${resource_id}
        description: "Retrieve the created resource"
        depends_on:
          - create_resource
        expect:
          status: [200]
          body:
            id: "${resource_id}"
            name: "${resource_name}"
      
      - name: update_resource
        endpoint: PUT /resources/${resource_id}
        description: "Update the resource"
        depends_on:
          - get_resource
        request:
          body:
            name: "Updated Resource"
            description: "Updated by workflow test"
        expect:
          status: [200]
      
      - name: delete_resource
        endpoint: DELETE /resources/${resource_id}
        description: "Delete the resource"
        depends_on:
          - update_resource
        expect:
          status: [204]
      
      - name: verify_deleted
        endpoint: GET /resources/${resource_id}
        description: "Verify resource was deleted"
        depends_on:
          - delete_resource
        expect:
          status: [404]
    
    teardown:
      - name: cleanup_resource
        endpoint: DELETE /resources/${resource_id}
        condition: "${resource_id} != null"
        ignore_failure: true
'''

USER_CRUD_TEMPLATE = '''# User CRUD Workflow Template
workflows:
  - name: user_crud
    description: "Complete user lifecycle test"
    tags:
      - users
      - crud
      - critical
    
    variables:
      test_email: "test-${timestamp}@example.com"
    
    steps:
      - name: create_user
        endpoint: POST /users
        description: "Create a new user"
        request:
          body:
            name: "${faker:name}"
            email: "${test_email}"
            role: "member"
        expect:
          status: [201]
          body:
            email: "${test_email}"
        extract:
          user_id: $.id
          user_email: $.email
      
      - name: get_user
        endpoint: GET /users/${user_id}
        description: "Retrieve the created user"
        depends_on:
          - create_user
        expect:
          status: [200]
          body:
            id: "${user_id}"
            email: "${user_email}"
      
      - name: update_user
        endpoint: PUT /users/${user_id}
        description: "Update user details"
        depends_on:
          - get_user
        request:
          body:
            name: "Updated User Name"
            role: "admin"
        expect:
          status: [200]
          body:
            role: "admin"
      
      - name: list_users
        endpoint: GET /users
        description: "List all users"
        depends_on:
          - update_user
        request:
          query:
            limit: 10
        expect:
          status: [200]
          body:
            "${length}": "${gte:1}"
      
      - name: delete_user
        endpoint: DELETE /users/${user_id}
        description: "Delete the user"
        depends_on:
          - list_users
        expect:
          status: [204]
      
      - name: verify_deleted
        endpoint: GET /users/${user_id}
        description: "Verify user was deleted"
        depends_on:
          - delete_user
        expect:
          status: [404]
    
    teardown:
      - name: cleanup_user
        endpoint: DELETE /users/${user_id}
        condition: "${user_id} != null"
        ignore_failure: true
'''

ORDER_WORKFLOW_TEMPLATE = '''# Order Processing Workflow Template
workflows:
  - name: order_processing
    description: "Complete order lifecycle from creation to fulfillment"
    tags:
      - orders
      - e-commerce
      - integration
    
    settings:
      timeout: 300
    
    variables:
      quantity: 2
    
    setup:
      - name: get_product
        endpoint: GET /products
        description: "Get an available product"
        request:
          query:
            in_stock: true
            limit: 1
        expect:
          status: [200]
        extract:
          product_id: $.items[0].id
          product_price: $.items[0].price
    
    steps:
      - name: create_customer
        endpoint: POST /customers
        description: "Create a test customer"
        request:
          body:
            name: "${faker:name}"
            email: "${faker:email}"
            phone: "${faker:phone}"
        expect:
          status: [201]
        extract:
          customer_id: $.id
      
      - name: create_order
        endpoint: POST /orders
        description: "Create a new order"
        depends_on:
          - create_customer
        request:
          body:
            customer_id: "${customer_id}"
            items:
              - product_id: "${product_id}"
                quantity: "${quantity}"
        expect:
          status: [201]
          body:
            status: "pending"
        extract:
          order_id: $.id
          order_total: $.total
      
      - name: get_order
        endpoint: GET /orders/${order_id}
        description: "Retrieve order details"
        depends_on:
          - create_order
        expect:
          status: [200]
          body:
            id: "${order_id}"
            customer_id: "${customer_id}"
      
      - name: process_payment
        endpoint: POST /orders/${order_id}/pay
        description: "Process payment for the order"
        depends_on:
          - get_order
        request:
          body:
            payment_method: "credit_card"
            card_token: "tok_test_${random:length=16}"
        expect:
          status: [200]
          body:
            payment_status: "completed"
      
      - name: wait_for_processing
        endpoint: GET /orders/${order_id}
        description: "Wait for order to be processed"
        depends_on:
          - process_payment
        poll:
          interval: 2
          timeout: 30
          until:
            body:
              status:
                - "processing"
                - "shipped"
                - "completed"
      
      - name: verify_order_complete
        endpoint: GET /orders/${order_id}
        description: "Verify order is complete"
        depends_on:
          - wait_for_processing
        expect:
          status: [200]
          custom:
            - "response.body.status != 'pending'"
    
    teardown:
      - name: cancel_order
        endpoint: POST /orders/${order_id}/cancel
        condition: "${order_id} != null"
        ignore_failure: true
      
      - name: cleanup_customer
        endpoint: DELETE /customers/${customer_id}
        condition: "${customer_id} != null"
        ignore_failure: true
'''

AUTH_WORKFLOW_TEMPLATE = '''# Authentication Workflow Template
workflows:
  - name: auth_flow
    description: "Test authentication and authorization flows"
    tags:
      - auth
      - security
      - critical
    
    steps:
      - name: register_user
        endpoint: POST /auth/register
        description: "Register a new user"
        request:
          body:
            email: "test-${timestamp}@example.com"
            password: "SecurePass123!"
            name: "${faker:name}"
        expect:
          status: [201]
        extract:
          user_id: $.user.id
          user_email: $.user.email
      
      - name: login
        endpoint: POST /auth/login
        description: "Login with credentials"
        depends_on:
          - register_user
        request:
          body:
            email: "${user_email}"
            password: "SecurePass123!"
        expect:
          status: [200]
          body:
            token: "${type:string}"
        extract:
          access_token: $.token
          refresh_token: $.refresh_token
      
      - name: access_protected_resource
        endpoint: GET /users/me
        description: "Access protected resource with token"
        depends_on:
          - login
        request:
          headers:
            Authorization: "Bearer ${access_token}"
        expect:
          status: [200]
          body:
            id: "${user_id}"
      
      - name: refresh_token
        endpoint: POST /auth/refresh
        description: "Refresh the access token"
        depends_on:
          - access_protected_resource
        request:
          body:
            refresh_token: "${refresh_token}"
        expect:
          status: [200]
        extract:
          new_access_token: $.token
      
      - name: access_with_new_token
        endpoint: GET /users/me
        description: "Access with refreshed token"
        depends_on:
          - refresh_token
        request:
          headers:
            Authorization: "Bearer ${new_access_token}"
        expect:
          status: [200]
      
      - name: logout
        endpoint: POST /auth/logout
        description: "Logout and invalidate token"
        depends_on:
          - access_with_new_token
        request:
          headers:
            Authorization: "Bearer ${new_access_token}"
        expect:
          status: [200, 204]
      
      - name: verify_token_invalid
        endpoint: GET /users/me
        description: "Verify token is invalidated after logout"
        depends_on:
          - logout
        request:
          headers:
            Authorization: "Bearer ${new_access_token}"
        expect:
          status: [401]
    
    teardown:
      - name: cleanup_user
        endpoint: DELETE /users/${user_id}
        condition: "${user_id} != null"
        ignore_failure: true
'''

TEMPLATES = {
    "crud_basic": CRUD_BASIC_TEMPLATE,
    "user_crud": USER_CRUD_TEMPLATE,
    "order_processing": ORDER_WORKFLOW_TEMPLATE,
    "auth_flow": AUTH_WORKFLOW_TEMPLATE,
}


def get_template(name: str) -> str:
    """Get a workflow template by name.
    
    Args:
        name: Template name.
        
    Returns:
        Template content as a string.
    """
    return TEMPLATES.get(name, CRUD_BASIC_TEMPLATE)


def list_templates() -> list[str]:
    """List available template names."""
    return list(TEMPLATES.keys())

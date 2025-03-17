from fastapi import FastAPI, HTTPException, status
from datetime import date
from finance_models import FinanceRequest, FinanceResponse, FinanceRecord

app = FastAPI(
    title="Finance API",
    description="A simple API for Finance functionality",
    version="1.0.0",
)

@app.post(
    "/get_order_history",
    response_model=FinanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Request order history",
    description="Endpoint to a customer's order history",
)
async def get_order_history(request: FinanceRequest):
    """
    Customer's order history
    
    - **email**: Email address of the customer
    - **Returns**:
    """    
    print("-"*50)
    print(f"Order History: {request.email}")
    print("-"*50)
    
    # Dummy Data
    return FinanceResponse(
        records=[  # Ensuring it's a list inside `records`
            FinanceRecord(
                order_id=100,
                customer_name="Customer Name",
                order_date=date.today(),
                order_number="ORD-1234",
                status="Completed",
                total_amount=100.00,
            )
        ]
    )

@app.post(
    "/get_invoice_history",
    response_model=FinanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Request invoice history",
    description="Endpoint to a customer's invoices",
)
async def get_invoice_history(request: FinanceRequest):
    """
    Customer's invoices
    
    - **email**: Email address of the customer
    - **Returns**:
    """    
    print("-"*50)
    print(f"Invoice Request: {request.email}")
    print("-"*50)
    
    # Dummy Data
    return FinanceResponse(
        records=[  # Ensuring it's a list inside `records`
            FinanceRecord(
                order_id=100,
                customer_name="Customer Name",
                order_date=date.today(),
                order_number="ORD-1234",
                status="Completed",
                total_amount=100.00,
            )
        ]
    )

@app.post(
    "/start_duplicate_charge_dispute",
    response_model=FinanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Starts duplicate charge dispute",
    description="Endpoint to beginning duplicate charge dispute process",
)
async def start_duplicate_charge_dispute(request: FinanceRequest):
    """
    Customer issues with duplicate_charge
    
    - **email**: Email address of the customer
    - **Returns**:
    """    
    print("-"*50)
    print(f"duplicate_charge: {request.email}")
    print("-"*50)
    
    # Dummy Data
    return FinanceResponse(
        records=[  # Ensuring it's a list inside `records`
            FinanceRecord(
                order_id=100,
                customer_name="Customer Name",
                order_date=date.today(),
                order_number="ORD-1234",
                status="Completed",
                total_amount=100.00,
            )
        ]
    )

@app.post(
    "/find_lost_receipt",
    response_model=FinanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Starts lost receipt finding process",
    description="Endpoint to for lost receipts",
)
async def find_lost_receipt(request: FinanceRequest):
    """
    Customer issues with lost_receipt
    
    - **email**: Email address of the customer
    - **Returns**:
    """    
    print("-"*50)
    print(f"lost_receipt: {request.email}")
    print("-"*50)
    
    # Dummy Data
    return FinanceResponse(
        records=[  # Ensuring it's a list inside `records`
            FinanceRecord(
                order_id=100,
                customer_name="Customer Name",
                order_date=date.today(),
                order_number="ORD-1234",
                status="Completed",
                total_amount=100.00,
            )
        ]
    )


@app.get("/")
async def root():
    """Root endpoint that redirects to the API documentation."""
    return {"message": "Welcome to the Finance API. Visit /docs for the API documentation."}

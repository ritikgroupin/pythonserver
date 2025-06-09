from fastapi import FastAPI, Request,HTTPException
from pydantic import BaseModel, EmailStr
from fpdf import FPDF
from fastapi.responses import FileResponse, JSONResponse
import uuid
import os
import requests
import smtplib
from email.message import EmailMessage
from jinja2 import Environment, FileSystemLoader

TEMPLATE_ENV = Environment(loader=FileSystemLoader("templates"))

app = FastAPI()

EMAIL_CONFIG = {
    'smtp_server': 'smtp.azurecomm.net',
    'smtp_port': 587,
    'sender': 'donotreply@groupinsolutionsinc.com',
    'sender_name': 'GroupIN',
    'reply_to': 'donotreply@groupinsolutionsinc.com',
    'reply_to_name': 'GroupIN',
    'username': 'groupinapp-comms.0ce06a06-cfc4-4be4-8255-5238c4f198d3.c4e551c2-f4e7-4e37-9a6a-bad853320992',
    'password': 'BrZ8Q~JdjWCnR9hrD2sSOb1mEfn6lkx0wg7y4c_.'
}

FONT_URL = "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf"
FONT_FILE = "DejaVuSans.ttf"

# Download font if it doesn't exist
def ensure_font():
    if not os.path.exists(FONT_FILE):
        print("Downloading DejaVuSans.ttf...")
        url = "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf"
        response = requests.get(url)
        response.raise_for_status()  # Raise error if download fails
        with open(FONT_FILE, "wb") as f:
            f.write(response.content)

class PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_page()
        self.set_font("Arial", size=12)


@app.post("/generate-receipt")
async def generate_receipt(request: Request):
    data = await request.json()

    orderdata = data.get("orderdata", {})
    ownerdata = data.get("ownerdata", {})
    # print("Received orderdata:", orderdata)
    # print("Received ownerdata:", ownerdata)

    filename = f"receipt_{uuid.uuid4()}.pdf"

    # Generate PDF
    pdf = FPDF()
    pdf = PDF()
    pdf.set_font("Arial", size=14)  # ✅ No need to call add_font

    pdf.cell(200, 10, txt="Receipt", ln=True, align='C')

    # Owner Info
    pdf.set_font("Arial", size=14)  
    pdf.cell(200, 10, txt="--- Owner Information ---", ln=True)
    pdf.set_font("Arial", size=14)  
    pdf.cell(200, 10, txt=f"Name: {ownerdata.get('name', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Mobile: {ownerdata.get('mobile_number', 'N/A')}", ln=True)
    aadhaar_details = ownerdata.get("aadhaar_details", {})
    if isinstance(aadhaar_details, str):
        import json
        aadhaar_details = json.loads(aadhaar_details)
    pdf.cell(200, 10, txt=f"Name: {aadhaar_details.get('name', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Gender: {aadhaar_details.get('gender', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"DOB: {aadhaar_details.get('dob', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Address: {aadhaar_details.get('address', 'N/A')}", ln=True)

    bank_details = ownerdata.get("bank_details", {})
    if isinstance(bank_details, str):
        import json
        bank_details = json.loads(bank_details)
    pdf.cell(200, 10, txt=f"Bank: {bank_details.get('bank_name', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Account No: {bank_details.get('account_number', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"IFSC: {bank_details.get('ifsc', 'N/A')}", ln=True)

    pdf.ln(10)
    pdf.cell(200, 10, txt="--- Order Details ---", ln=True)
    pdf.cell(200, 10, txt=f"Order ID: {orderdata.get('order_id', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Ordered Date: {orderdata.get('ordered_date', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Payment Status: {orderdata.get('payment_status', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Order Value: Rs.{orderdata.get('order_value', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Status: {orderdata.get('status', 'N/A')}", ln=True)

    product = orderdata.get("products", {})
    pdf.cell(200, 10, txt="--- Product Details ---", ln=True)
    pdf.cell(200, 10, txt=f"Product Name: {product.get('product_name', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Price: Rs.{product.get('product_price', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Color: {product.get('color', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Quantity: {product.get('quantity', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Description: {product.get('description', 'N/A')}", ln=True)

    address = orderdata.get("address", {})
    pdf.cell(200, 10, txt="--- Delivery Address ---", ln=True)
    pdf.cell(200, 10, txt=f"Name: {address.get('full_name', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Phone: {address.get('phone_number', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Address: {address.get('street_address', '')}, {address.get('city', '')}, {address.get('state_province', '')}, {address.get('postal_code', '')}", ln=True)

    # Save PDF to bytes
    pdf_bytes = pdf.output(dest='S')

    try:
        url = upload_pdf_to_azure(filename, pdf_bytes)
        return JSONResponse(content={"receipt_url":url})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

  
    
def upload_pdf_to_azure(filename: str, pdf_bytes: bytes) -> str:
    ACCOUNT_NAME = "groupinappstorage"
    CONTAINER_NAME = "the-vns-dev-media-bucket"
    BASE_URL = "https://groupinappstorage.blob.core.windows.net"
    SAS_TOKEN = (
        "sp=racwdl&st=2025-01-31T02:32:19Z&se=2026-01-31T10:32:19Z&spr=https"
        "&sv=2022-11-02&sr=c&sig=%2FLvVFFo1PyA5AgA%2BODU1d3JCSwGG1GJJgBu9FvIcddY%3D"
    )

    # Construct the full URL
    blob_path = f"{CONTAINER_NAME}/{filename}"
    full_url = f"{BASE_URL}/{blob_path}?{SAS_TOKEN}"

    headers = {
        "x-ms-blob-type": "BlockBlob",
        "Content-Type": "application/pdf",
        "Content-Length": str(len(pdf_bytes)),
        "x-ms-version": "2020-10-02"
    }

    response = requests.put(full_url, headers=headers, data=pdf_bytes)

    if response.status_code == 201:
        return full_url
    else:
        raise Exception(f"Upload failed: {response.status_code} - {response.text}")
    
class EmailRequest(BaseModel):
    to: EmailStr
    subject: str
    content: str


def render_template(template_name: str, context: dict) -> str:
    try:
        template = TEMPLATE_ENV.get_template(template_name)
        return template.render(context)
    except Exception as e:
        raise Exception(f"Template rendering error: {e}")
    
    
class TemplatedEmailRequest(BaseModel):
    to: EmailStr
    subject: str
    template_name: str  # like "form_submission.html"
    context: dict 
    
@app.post("/send-templated-email")
async def send_templated_email_api(payload: TemplatedEmailRequest):
    try:
        html_content = render_template(payload.template_name, payload.context)
        success = send_email(payload.to, payload.subject, html_content)
        if success:
            return {"message": "Templated email sent successfully!"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send email")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Email sending logic
def send_email(to: str, subject: str, content: str) -> bool:
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f"{EMAIL_CONFIG['sender_name']} <{EMAIL_CONFIG['sender']}>"
    msg['To'] = to
    msg['Reply-To'] = f"{EMAIL_CONFIG['reply_to_name']} <{EMAIL_CONFIG['reply_to']}>"
    msg.set_content("This email requires an HTML-compatible email client to view properly.")
    msg.add_alternative(content, subtype="html")

    try:
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], 587) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_CONFIG['username'], EMAIL_CONFIG['password'])
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

# FastAPI route
@app.post("/send-email")
async def send_email_api(payload: EmailRequest):
    success = send_email(payload.to, payload.subject, payload.content)
    if success:
        return {"message": "Email sent successfully!"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email")
@app.get("/")
def root():
    return {"message": "PDF Receipt Generator is running."}

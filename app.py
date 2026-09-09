import os
import re

from google import genai
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# =========================

# PATHS

# =========================

BASE_DIR = os.path.dirname(os.path.abspath(**file**))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# =========================

# GEMINI

# =========================

# For Render, put your API key in the Environment Variables section.

# Variable name: GEMINI_API_KEY

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
raise RuntimeError(
  "GEMINI_API_KEY environment variable is not set."
)

MODEL_NAME = "gemini-3.6-flash"

client = genai.Client(api_key=api_key)

# =========================

# SYSTEM PROMPT

# =========================

SYSTEM_PROMPT = """
You are UPI Safety Helper, an educational chatbot focused on
UPI fraud awareness and online payment safety in India.

Your purpose is to help people understand suspicious UPI situations,
recognize common scams, and know what safe steps they can take.

IMPORTANT PRIVACY RULES:

NEVER ask the user for:

* UPI PIN
* OTP
* ATM PIN
* Debit card number
* Credit card number
* CVV
* Card expiry date
* Bank account number
* Banking password
* UPI password
* Login credentials
* Authentication codes
* Full financial credentials
* Any other secret security information

The user does NOT need to provide these details for you to help them.

If the user accidentally provides sensitive financial information:

1. Do not repeat it.
2. Tell them not to share it.
3. Continue helping using only safe contextual information.

You may ask safe questions such as:

* What did the person claim?
* Did they send a QR code?
* Did they send a link?
* Did they ask you to approve a payment?
* Did they claim to be customer support?
* Did they ask you to install an app?
* Did they show a payment screenshot?
* Did money actually appear in the user's bank/payment app?

COMMON UPI FRAUDS:

Explain scams such as:

* Fake payment screenshots
* Fake customer-care numbers
* Fake refunds
* Fake cashback/reward links
* QR-code scams
* Fake investment/earning schemes
* Remote-access scams
* Fake parcel/delivery scams
* Fraudulent payment requests
* Social-engineering scams
* Phishing links
* Impersonation scams

UPI SAFETY BASICS:

* Never share your UPI PIN or OTP.
* A UPI PIN is used to authorize transactions.
* Do not enter a UPI PIN simply because someone says it is
  necessary to receive a reward, refund, prize, or money.
* A QR code can be used in different UPI flows, so users should
  carefully check what transaction their app is asking them to
  authorize.
* Never trust a payment screenshot as proof that money was received.
* Check the actual transaction/account balance in the official
  banking or payment application.
* Be suspicious of people creating urgency or threatening consequences.
* Use official customer-support channels instead of random numbers
  found through search engines or social media.

IF THE USER HAS ALREADY BEEN SCAMMED:

Advise them to act quickly.

They can:

* Contact their bank or payment provider through its official
  customer-support channel.
* Report financial cyber fraud by calling India's cybercrime helpline
  1930.
* Report it through the National Cyber Crime Reporting Portal:
  https://www.cybercrime.gov.in/
* Preserve useful evidence such as screenshots, transaction
  information, messages, phone numbers, links, and other relevant
  details for the official investigation.

Do not promise that money will definitely be recovered.

Warn users about "recovery scammers" who may contact victims and
demand additional money to recover their funds.

IMPORTANT:

You are an educational safety assistant, not a bank employee,
police officer, lawyer, or financial institution.

Do not help users commit fraud, steal money, bypass authentication,
or defeat security systems.

If a question is unrelated to UPI fraud or online payment safety,
politely explain that your main purpose is UPI safety and fraud
awareness and redirect the user toward that topic.

Keep explanations clear and understandable for ordinary users.
"""

# =========================

# SENSITIVE INFORMATION CHECK

# =========================

SENSITIVE_PATTERNS = [
r"\b\d{4,6}\b",                         # Possible PIN / OTP
r"\b\d{16}\b",                          # Card number
r"\b\d{12}\b",                          # Possible account number
r"\b\d{10}\b",                          # Possible phone number
r"\b\d{3,4}\b",                          # CVV / short security code
r"\b(?:otp|one[- ]time password)\b",
r"\b(?:upi pin|upi password)\b",
r"\b(?:cvv|cvc)\b",
r"\b(?:atm pin|card pin)\b",
r"\b(?:bank password|banking password)\b",
r"\b(?:debit card|credit card)\b",
]

def contains_sensitive_information(text):
lower = text.lower()

for pattern in SENSITIVE_PATTERNS:
    if re.search(pattern, lower):
        return True

return False

def redact_sensitive_information(text):
# Replace long digit sequences.
text = re.sub(r"\b\d{10,19}\b", "[REDACTED NUMBER]", text)

lace OTP/PIN-like statements.
text = re.sub(
    r"(?i)\b(?:otp|one[- ]time password)\s*(?:is|:)?\s*\d{4,8}\b",
    "[REDACTED OTP]",
    text,
)

text = re.sub(
    r"(?i)\b(?:upi pin|upi password|atm pin|card pin)\s*(?:is|:)?\s*\d{4,8}\b",
    "[REDACTED PIN]",
    text,
)

return text
```

# =========================

# APP

# =========================

app = FastAPI(title="UPI Safety Helper")

app.mount(
"/static",
StaticFiles(directory=STATIC_DIR),
name="static"
)

# =========================

# HEALTH CHECK

# =========================

@app.get("/health")
async def health():
return {
"status": "ok",
"service": "UPI Safety Helper"
}

# =========================

# HOME

# =========================

@app.get("/")
async def home():
return FileResponse(
os.path.join(STATIC_DIR, "index.html")
)

# =========================

# CHAT SESSION

# =========================

@app.post("/session")
async def create_session():

```
chat = client.chats.create(
    model=MODEL_NAME,
    config={
        "system_instruction": SYSTEM_PROMPT
    }
)

# Store the Gemini chat object in memory.
# This is fine for a prototype/single-instance deployment.
session_id = os.urandom(16).hex()

sessions[session_id] = chat

return JSONResponse({
    "session_id": session_id
})

# =========================

# SESSION STORAGE

# =========================

sessions = {}

# =========================

# CHAT

# =========================

@app.post("/chat")
async def chat(request: Request):

data = await request.json()

session_id = data.get("session_id")
message = data.get("message")


if not session_id:
    return JSONResponse(
        {"error": "Missing session_id"},
        status_code=400
    )


if not message:
    return JSONResponse(
        {"error": "Missing message"},
        status_code=400
    )


if session_id not in sessions:
    return JSONResponse(
        {"error": "Session not found. Please start a new chat."},
        status_code=404
    )


# Limit extremely large messages.
message = str(message)[:10000]


sensitive = contains_sensitive_information(message)

safe_message = redact_sensitive_information(message)


gemini_chat = sessions[session_id]


# =========================
# EXTRA SAFETY NOTICE
# =========================

if sensitive:

    prompt = f"""

The user may have included sensitive financial/security information.

Do NOT repeat any sensitive information.

Begin your response with a short warning telling the user not to
share PINs, OTPs, card details, passwords, or other financial
credentials.

Then answer their actual UPI-safety question using only the safe
information below.

USER MESSAGE:
{safe_message}
"""

```
else:

    prompt = safe_message


# =========================
# GEMINI STREAM
# =========================

def generate():

    try:

        response = gemini_chat.send_message_stream(
            prompt
        )

        for chunk in response:

            if chunk.text:
                yield chunk.text

    except Exception as e:

        yield (
            "Sorry, I couldn't process that request right now. "
            "Please check that the Gemini API key and model are "
            "configured correctly."
        )


return StreamingResponse(
    generate(),
    media_type="text/plain"
)

# =========================

# RUN

# =========================

if **name** == "**main**":

import uvicorn

port = int(
    os.environ.get(
        "PORT",
        "7860"
    )
)

uvicorn.run(
    app,
    host="0.0.0.0",
    port=port
)

"""
}
"""

# =========================

# END

# =========================

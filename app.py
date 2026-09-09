import os
import uuid
import sqlite3

from google import genai
from fastapi import Fast
API, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


# -----------------------------
# Configuration
# -----------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "memory.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")

MODEL_NAME = "gemini-3.6-flash"

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

client = genai.Client(api_key=api_key)


# -----------------------------
# FastAPI app
# -----------------------------

app = FastAPI(title="UPI Safety Chatbot")

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static"
)

sessions = {}


# -----------------------------
# Database
# -----------------------------

def init_db():
    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            memory TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()


init_db()


def get_memories(user_id):
    conn = sqlite3.connect(DB_FILE)

    rows = conn.execute(
        """
        SELECT id, memory
        FROM memories
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 50
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    return rows


def add_memory(user_id, memory):
    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        """
        INSERT INTO memories (user_id, memory)
        VALUES (?, ?)
        """,
        (user_id, memory)
    )

    conn.commit()
    conn.close()


def delete_memory(user_id, memory_id):
    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        """
        DELETE FROM memories
        WHERE id = ? AND user_id = ?
        """,
        (memory_id, user_id)
    )

    conn.commit()
    conn.close()


# -----------------------------
# Routes
# -----------------------------

@app.get("/")
async def home():
    return FileResponse(
        os.path.join(STATIC_DIR, "index.html")
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


# -----------------------------
# Create chat session
# -----------------------------

@app.post("/session")
async def create_session(request: Request):
    user_id = request.cookies.get("user_id")

    if not user_id:
        user_id = str(uuid.uuid4())

    session_id = str(uuid.uuid4())

    sessions[session_id] = {
        "user_id": user_id,
        "chat": client.chats.create(
            model=MODEL_NAME
        )
    }

    response = JSONResponse(
        {
            "session_id": session_id
        }
    )

    response.set_cookie(
        key="user_id",
        value=user_id,
        max_age=60 * 60 * 24 * 365 * 5,
        httponly=True,
        samesite="lax"
    )

    return response


# -----------------------------
# Memories
# -----------------------------

@app.get("/memories")
async def view_memories(request: Request):
    user_id = request.cookies.get("user_id")

    if not user_id:
        return {"memories": []}

    memories = get_memories(user_id)

    return {
        "memories": [
            {
                "id": memory_id,
                "memory": memory
            }
            for memory_id, memory in memories
        ]
    }


# -----------------------------
# Chat
# -----------------------------

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()

    session_id = data.get("session_id")
    message = data.get("message")

    if not session_id:
        return {"error": "Missing session_id"}

    if not message:
        return {"error": "Missing message"}

    if session_id not in sessions:
        return {"error": "Session not found"}

    session = sessions[session_id]

    user_id = session["user_id"]
    gemini_chat = session["chat"]

    lower = message.lower().strip()


    # -------------------------
    # Remember command
    # -------------------------

    memory = None

    if lower.startswith("remember that "):
        memory = message[len("remember that "):].strip()

    elif lower.startswith("remember "):
        memory = message[len("remember "):].strip()

    elif lower.startswith("please remember that "):
        memory = message[len("please remember that "):].strip()


    if memory:
        add_memory(user_id, memory)

        return StreamingResponse(
            iter(
                [
                    f"Got it! I'll remember: {memory} 🧠"
                ]
            ),
            media_type="text/plain"
        )


    # -------------------------
    # Forget command
    # -------------------------

    if lower.startswith("forget that "):
        target = message[len("forget that "):].strip()

    elif lower.startswith("forget "):
        target = message[len("forget "):].strip()

    else:
        target = None


    if target:
        memories = get_memories(user_id)
        deleted = False

        for memory_id, stored_memory in memories:
            if target.lower() in stored_memory.lower():
                delete_memory(user_id, memory_id)
                deleted = True

        if deleted:
            return StreamingResponse(
                iter(
                    [
                        "Okay, I'll forget that. 🗑️"
                    ]
                ),
                media_type="text/plain"
            )

        return StreamingResponse(
            iter(
                [
                    "I couldn't find that memory."
                ]
            ),
            media_type="text/plain"
        )


    # -------------------------
    # Load memories
    # -------------------------

    memories = get_memories(user_id)


    # -------------------------
    # UPI Safety Prompt
    # -------------------------

    safety_rules = """
You are a helpful AI chatbot focused on UPI fraud awareness
and digital payment safety in India.

Your job is to educate users about UPI scams, fraud prevention,
safe digital payments, and what to do after a suspected scam.

Important safety rules:

- Never ask the user for their UPI PIN.
- Never ask for an OTP.
- Never ask for a bank password.
- Never ask for a card number.
- Never ask for a CVV.
- Never ask for account passwords.
- Never ask users to share confidential financial credentials.
- Never tell users to reveal sensitive banking information in chat.
- If someone has lost money to fraud, advise them to contact
  their bank or payment provider and report the incident through
  the appropriate official cybercrime reporting channels.
- Explain scams clearly and simply.
- Do not help users commit fraud.
- Do not help users bypass payment security.
- If the user asks whether something is suspicious, explain the
  warning signs and suggest safe verification steps.

Never request sensitive financial credentials even if the user
voluntarily offers them.

If the user asks for help after a suspected financial fraud,
recommend contacting their bank/payment provider promptly and
using India's official cybercrime reporting channels, including
1930 and cybercrime.gov.in when appropriate.
"""


    # -------------------------
    # Build Gemini prompt
    # -------------------------

    if memories:
        memory_text = "\n".join(
            f"- {memory}"
            for _, memory in memories
        )

        prompt = f"""
{safety_rules}

The user has explicitly asked you to remember these facts:

{memory_text}

Use these memories only when they are relevant to the conversation.

Do not mention the memory system unless the user asks about it.

USER MESSAGE:
{message}
"""

    else:
        prompt = f"""
{safety_rules}

USER MESSAGE:
{message}
"""


    # -------------------------
    # Stream Gemini response
    # -------------------------

    def generate():
        try:
            response = gemini_chat.send_message_stream(prompt)

            for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as error:
            yield f"Sorry, something went wrong: {error}"


    return StreamingResponse(
        generate(),
        media_type="text/plain"
    )


# -----------------------------
# Run server
# -----------------------------

if __name__ == "__main__":
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

import json
import os
import secrets
import sqlite3

from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import jwt

from passlib.context import CryptContext

from fastapi import (
    FastAPI,
    Request,
    HTTPException,
    Form,
    File,
    UploadFile,
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from google import genai
from google.genai import types


BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# SETTINGS
# ============================================================

class Settings(BaseSettings):

    secret_key: str = secrets.token_urlsafe(32)

    gemini_api_key: str | None = None

    gemini_model: str = "gemini-2.5-flash"

    database_path: str = str(BASE_DIR / "data" / "pocketsmart.db")

    max_upload_mb: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()


# ============================================================
# DIRECTORIES
# ============================================================

Path(settings.database_path).parent.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# PASSWORD SECURITY
# ============================================================

pwd = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# ============================================================
# DATABASE
# ============================================================

def db():

    connection = sqlite3.connect(
        settings.database_path
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def init_db():

    connection = db()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            planner TEXT NOT NULL,
            request_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
        );
        """
    )

    connection.commit()
    connection.close()


# ============================================================
# JWT
# ============================================================

def token_for(user):

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user["id"]),
        "name": user["name"],
        "email": user["email"],
        "iat": now,
        "exp": now + timedelta(hours=8)
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256"
    )


def user_from(request: Request):

    authorization = request.headers.get(
        "authorization",
        ""
    )

    if not authorization.lower().startswith("bearer "):

        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    token = authorization.split(
        " ",
        1
    )[1]

    try:

        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"]
        )

    except jwt.PyJWTError:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    connection = db()

    user = connection.execute(
        """
        SELECT id, name, email
        FROM users
        WHERE id=?
        """,
        (
            int(payload["sub"]),
        )
    ).fetchone()

    connection.close()

    if not user:

        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return dict(user)


# ============================================================
# PYDANTIC MODELS
# ============================================================

class Register(BaseModel):

    name: str = Field(
        min_length=2,
        max_length=80
    )

    email: str

    password: str = Field(
        min_length=8,
        max_length=128
    )


class Login(BaseModel):

    email: str

    password: str


class Home(BaseModel):

    budget: float = Field(gt=0)

    currency: str = "INR"

    rooms: list[str] = Field(
        min_length=1
    )

    style: str = "modern"

    notes: str = ""


class Party(BaseModel):

    budget: float = Field(gt=0)

    currency: str = "INR"

    guests: int = Field(gt=0)

    event_type: str

    venue: str = "Not decided"

    city: str = ""

    preferences: str = ""


# ============================================================
# PLATFORM SEARCH LINKS
# ============================================================

PLATFORMS = {

    "Amazon":
        "https://www.amazon.in/s?k={}",

    "Flipkart":
        "https://www.flipkart.com/search?q={}",

    "IKEA":
        "https://www.ikea.com/in/en/search/?q={}",

    "Swiggy":
        "https://www.swiggy.com/search?query={}",

    "Zomato":
        "https://www.zomato.com/search?query={}",

    "OYO":
        "https://www.oyorooms.com/search?location={}"
}


def link(platform, query):

    encoded = quote_plus(query)

    template = PLATFORMS.get(
        platform,
        "https://www.google.com/search?q={}"
    )

    return template.format(encoded)


# ============================================================
# FALLBACK RECOMMENDATION ENGINE
# ============================================================

def fallback(planner, data):

    budget = float(
        data["budget"]
    )

    currency = data.get(
        "currency",
        "INR"
    )


    # --------------------------------------------------------
    # HOME
    # --------------------------------------------------------

    if planner == "home":

        allocations = {

            "furniture":
                budget * 0.40,

            "lighting":
                budget * 0.15,

            "decor":
                budget * 0.20,

            "storage":
                budget * 0.15,

            "buffer":
                budget * 0.10
        }

        items = [

            (
                "Compact sofa",
                "furniture",
                allocations["furniture"] * 0.55,
                "Amazon"
            ),

            (
                "LED ceiling lights",
                "lighting",
                allocations["lighting"] * 0.55,
                "IKEA"
            ),

            (
                "Wall art set",
                "decor",
                allocations["decor"] * 0.55,
                "Amazon"
            ),

            (
                "Modular storage",
                "storage",
                allocations["storage"] * 0.65,
                "IKEA"
            )
        ]


    # --------------------------------------------------------
    # PARTY
    # --------------------------------------------------------

    elif planner == "party":

        allocations = {

            "food":
                budget * 0.45,

            "decoration":
                budget * 0.15,

            "venue":
                budget * 0.25,

            "entertainment":
                budget * 0.10,

            "buffer":
                budget * 0.05
        }

        items = [

            (
                "Catering package",
                "food",
                allocations["food"],
                "Zomato"
            ),

            (
                "Party decor",
                "decoration",
                allocations["decoration"],
                "Amazon"
            ),

            (
                "Venue search",
                "venue",
                allocations["venue"],
                "OYO"
            ),

            (
                "Dessert and snacks",
                "food",
                allocations["food"] * 0.20,
                "Swiggy"
            )
        ]


    # --------------------------------------------------------
    # JEWELRY
    # --------------------------------------------------------

    else:

        allocations = {

            "main_piece":
                budget * 0.55,

            "earrings":
                budget * 0.20,

            "bracelet":
                budget * 0.15,

            "buffer":
                budget * 0.10
        }

        items = [

            (
                "Occasion necklace",
                "main_piece",
                allocations["main_piece"],
                "Amazon"
            ),

            (
                "Matching earrings",
                "earrings",
                allocations["earrings"],
                "Flipkart"
            ),

            (
                "Minimal bracelet",
                "bracelet",
                allocations["bracelet"],
                "Amazon"
            )
        ]


    recommendations = []

    for title, category, price, platform in items:

        recommendations.append({

            "title": title,

            "category": category,

            "estimated_price":
                round(price, 2),

            "currency":
                currency,

            "reason":
                "Budget-aware starting option.",

            "platform":
                platform,

            "search_url":
                link(
                    platform,
                    title + " " + category
                )
        })


    return {

        "planner":
            planner,

        "budget":
            budget,

        "currency":
            currency,

        "summary":
            f"Starter plan for "
            f"{currency} {budget:,.2f}",

        "allocations": {
            key: round(value, 2)
            for key, value
            in allocations.items()
        },

        "recommendations":
            recommendations,

        "tips": [

            "Compare final delivered prices before buying.",

            "Keep a small contingency for unexpected costs."
        ],

        "source_mode":
            "fallback"
    }


# ============================================================
# GEMINI AI
# ============================================================

def ai(
    planner,
    data,
    image=None,
    mime=None
):

    # No API key = fallback

    if not settings.gemini_api_key:

        result = fallback(
            planner,
            data
        )

        result["source_mode"] = (
            "fallback-no-api-key"
        )

        return result


    schema = {

        "type": "object",

        "properties": {

            "planner": {
                "type": "string"
            },

            "budget": {
                "type": "number"
            },

            "currency": {
                "type": "string"
            },

            "summary": {
                "type": "string"
            },

            "allocations": {
                "type": "object",
                "additionalProperties": {
                    "type": "number"
                }
            },

            "recommendations": {

                "type": "array",

                "items": {

                    "type": "object",

                    "properties": {

                        "title":
                            {"type": "string"},

                        "category":
                            {"type": "string"},

                        "estimated_price":
                            {"type": "number"},

                        "currency":
                            {"type": "string"},

                        "reason":
                            {"type": "string"},

                        "platform":
                            {"type": "string"},

                        "search_url":
                            {"type": "string"}
                    },

                    "required": [

                        "title",
                        "category",
                        "estimated_price",
                        "currency",
                        "reason",
                        "platform",
                        "search_url"
                    ]
                }
            },

            "tips": {

                "type": "array",

                "items": {
                    "type": "string"
                }
            }
        },

        "required": [

            "planner",
            "budget",
            "currency",
            "summary",
            "allocations",
            "recommendations",
            "tips"
        ]
    }


    prompt = f"""
You are PocketSmart AI.

Create practical budget recommendations.

Planner:
{planner}

User input:
{json.dumps(data, ensure_ascii=False, indent=2)}

Rules:

1. Keep recommendations within the user's budget.
2. Never claim live inventory.
3. Never claim verified current prices.
4. Prices are estimates for planning.
5. Use recognizable Indian platforms.
6. Do not fabricate product IDs.
7. Return ONLY JSON matching the supplied schema.
"""


    try:

        client = genai.Client(
            api_key=settings.gemini_api_key
        )

        contents = [prompt]


        # Jewelry image analysis

        if image:

            contents.append(
                types.Part.from_bytes(
                    data=image,
                    mime_type=mime
                )
            )

            contents[0] += """

Analyze the attached outfit image only for broad:
- colours
- pattern
- formality
- visible style

Do not infer sensitive personal characteristics.
"""


        response = client.models.generate_content(

            model=settings.gemini_model,

            contents=contents,

            config=types.GenerateContentConfig(

                response_mime_type="application/json",

                response_schema=schema,

                temperature=0.4
            )
        )


        result = json.loads(
            response.text
        )

        result["source_mode"] = (
            "gemini:"
            + settings.gemini_model
        )

        return result


    except Exception:

        result = fallback(
            planner,
            data
        )

        result["source_mode"] = (
            "fallback-gemini-error"
        )

        return result


# ============================================================
# SAVE HISTORY
# ============================================================

def save(
    user,
    planner,
    data,
    result
):

    connection = db()

    cursor = connection.execute(

        """
        INSERT INTO history(
            user_id,
            planner,
            request_json,
            result_json
        )

        VALUES (?, ?, ?, ?)
        """,

        (
            user["id"],
            planner,
            json.dumps(data),
            json.dumps(result)
        )
    )

    connection.commit()

    history_id = cursor.lastrowid

    connection.close()

    result["history_id"] = history_id

    return result


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(

    title="PocketSmart AI",

    version="1.0.0",

    on_startup=[
        init_db
    ]
)


app.add_middleware(

    CORSMiddleware,

    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],

    allow_methods=["*"],

    allow_headers=["*"]
)


app.mount(

    "/static",

    StaticFiles(
        directory=str(BASE_DIR / "static")
    ),

    name="static"
)


templates = Jinja2Templates(
    directory=str(BASE_DIR / "app" / "templates")
)


def render_page(request: Request, page: str):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"page": page}
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "PocketSmart AI"
    }


# ============================================================
# WEB PAGES
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
def index(request: Request):

    return render_page(request, "home")


@app.get(
    "/register",
    response_class=HTMLResponse
)
def register_page(request: Request):

    return render_page(request, "register")


@app.get(
    "/login",
    response_class=HTMLResponse
)
def login_page(request: Request):

    return render_page(request, "login")


@app.get(
    "/dashboard",
    response_class=HTMLResponse
)
def dashboard_page(request: Request):

    return render_page(request, "dashboard")


@app.get(
    "/home-planner",
    response_class=HTMLResponse
)
def home_page(request: Request):

    return render_page(request, "home-planner")


@app.get(
    "/party-planner",
    response_class=HTMLResponse
)
def party_page(request: Request):

    return render_page(request, "party-planner")


@app.get(
    "/jewelry-planner",
    response_class=HTMLResponse
)
def jewelry_page(request: Request):

    return render_page(request, "jewelry-planner")


@app.get(
    "/history",
    response_class=HTMLResponse
)
def history_page(request: Request):

    return render_page(request, "history")


# ============================================================
# REGISTER
# ============================================================

@app.post("/api/auth/register")
def register(payload: Register):

    email = payload.email.strip().lower()

    connection = db()

    existing = connection.execute(
        "SELECT id FROM users WHERE email=?",
        (email,)
    ).fetchone()

    if existing:

        connection.close()

        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )


    cursor = connection.execute(

        """
        INSERT INTO users(
            name,
            email,
            password_hash
        )

        VALUES (?, ?, ?)
        """,

        (
            payload.name.strip(),
            email,
            pwd.hash(payload.password)
        )
    )

    connection.commit()

    user = {

        "id":
            cursor.lastrowid,

        "name":
            payload.name.strip(),

        "email":
            email
    }

    connection.close()


    return {

        "user":
            user,

        "access_token":
            token_for(user),

        "token_type":
            "bearer"
    }


# ============================================================
# LOGIN
# ============================================================

@app.post("/api/auth/login")
def login(payload: Login):

    connection = db()

    user = connection.execute(

        """
        SELECT *
        FROM users
        WHERE email=?
        """,

        (
            payload.email.strip().lower(),
        )
    ).fetchone()

    connection.close()


    if (
        not user
        or not pwd.verify(
            payload.password,
            user["password_hash"]
        )
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )


    clean_user = {

        "id": user["id"],

        "name": user["name"],

        "email": user["email"]
    }


    return {

        "user":
            clean_user,

        "access_token":
            token_for(clean_user),

        "token_type":
            "bearer"
    }


# ============================================================
# SESSION
# ============================================================

@app.get("/api/auth/session-info")
def session_info(
    request: Request
):

    return user_from(request)


# ============================================================
# HOME GENERATOR
# ============================================================

@app.post("/api/generate-home")
def generate_home(
    payload: Home,
    request: Request
):

    user = user_from(request)

    data = payload.model_dump()

    result = ai(
        "home",
        data
    )

    return save(
        user,
        "home",
        data,
        result
    )


# ============================================================
# PARTY GENERATOR
# ============================================================

@app.post("/api/generate-party")
def generate_party(
    payload: Party,
    request: Request
):

    user = user_from(request)

    data = payload.model_dump()

    result = ai(
        "party",
        data
    )

    return save(
        user,
        "party",
        data,
        result
    )


# ============================================================
# JEWELRY GENERATOR
# ============================================================

@app.post("/api/generate-jewelry")
async def generate_jewelry(

    request: Request,

    budget: float = Form(...),

    currency: str = Form("INR"),

    occasion: str = Form(...),

    style: str = Form("elegant"),

    metal: str = Form("any"),

    outfit_description: str = Form(""),

    outfit_image: UploadFile | None = File(None)
):

    user = user_from(request)


    if budget <= 0:

        raise HTTPException(
            status_code=422,
            detail="Budget must be greater than zero"
        )


    image = None

    mime = None


    if outfit_image:

        allowed_types = {

            "image/jpeg",

            "image/png",

            "image/webp"
        }


        if outfit_image.content_type not in allowed_types:

            raise HTTPException(

                status_code=400,

                detail="Use JPG, PNG or WEBP image"
            )


        image = await outfit_image.read()


        maximum = (
            settings.max_upload_mb
            * 1024
            * 1024
        )


        if len(image) > maximum:

            raise HTTPException(

                status_code=413,

                detail="Image too large"
            )


        mime = outfit_image.content_type


    data = {

        "budget":
            budget,

        "currency":
            currency,

        "occasion":
            occasion,

        "style":
            style,

        "metal":
            metal,

        "outfit_description":
            outfit_description
    }


    result = ai(

        "jewelry",

        data,

        image,

        mime
    )


    return save(

        user,

        "jewelry",

        data,

        result
    )


# ============================================================
# HISTORY
# ============================================================

@app.get("/api/history")
def history(request: Request):

    user = user_from(request)

    connection = db()

    rows = connection.execute(

        """
        SELECT
            id,
            planner,
            request_json,
            result_json,
            created_at

        FROM history

        WHERE user_id=?

        ORDER BY id DESC
        """,

        (
            user["id"],
        )
    ).fetchall()

    connection.close()


    return {

        "items":
            [dict(row) for row in rows]
    }


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
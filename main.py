from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests, os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["giftbot"]
users = db["users"]

app = FastAPI()
app.mount("/webapp", StaticFiles(directory="webapp"), name="webapp")

class BuyRequest(BaseModel):
    telegram_id: int
    amount: int  # сумма в XTR

@app.get("/", response_class=HTMLResponse)
async def get_webapp():
    return FileResponse("webapp/index.html")

@app.get("/pay/{amount}", response_class=HTMLResponse)
async def pay_with_amount(amount: int):
    path = os.path.join("webapp", "index.html")
    if not os.path.exists(path):
        return HTMLResponse("<h2>index.html не найден</h2>", status_code=404)

    with open(path, encoding="utf-8") as f:
        html = f.read().replace("{{AMOUNT}}", str(amount))
        return HTMLResponse(html)

@app.post("/create-xtr")
async def create_invoice(data: BuyRequest):
    if data.amount < 1:
        return {"error": "Amount must be positive"}
    
    payload = f"xtr_{data.telegram_id}_{data.amount}"
    
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/createInvoiceLink",
            json={
                "title": "Пополнение XTR",
                "description": f"{data.amount} XTR зачислятся на ваш баланс",
                "payload": payload,
                "currency": "XTR", 
                "prices": [{"label": "XTR Баланс", "amount": data.amount}],
                "provider_token": PROVIDER_TOKEN
            },
            timeout=10
        )
        
        print(f"[create-xtr] Request: {data.dict()}")
        print(f"[create-xtr] Response: {response.text}")
        
        result = response.json()
        
        if not result.get("ok"):
            print(f"❌ Telegram API Error: {result}")
            return {"error": "Failed to create invoice"}
            
        return result.get("result", {})
        
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return {"error": "Service unavailable"}

@app.post("/payment-success")
async def on_payment_success(req: Request):
    data = await req.json()
    print("\n[payment-success] payload:", data)
    payload = data.get("payload")
    if payload and payload.startswith("xtr_"):
        parts = payload.split("_")
        telegram_id = int(parts[1])
        amount = int(parts[2])
        users.update_one({"telegram_id": telegram_id}, {"$inc": {"balance.main": amount}}, upsert=True)
        print(f"[payment-success] +{amount} XTR → {telegram_id}")
    return {"ok": True}

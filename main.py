from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
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

class BuyRequest(BaseModel):
    telegram_id: int
    amount: int  # сумма в XTR

@app.get("/", response_class=HTMLResponse)
async def get_webapp():
    with open("webapp/index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.post("/create-xtr")
async def create_invoice(data: BuyRequest):
    payload = f"xtr_{data.telegram_id}_{data.amount}"
    response = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/createInvoiceLink", json={
        "title": "Пополнение XTR",
        "description": f"{data.amount} XTR зачислятся на ваш баланс",
        "payload": payload,
        "currency": "XTR",
        "prices": [{"label": "XTR Баланс", "amount": data.amount * 100}],
        "provider_token": PROVIDER_TOKEN
    })
    return response.json()["result"]

@app.post("/payment-success")
async def on_payment_success(req: Request):
    data = await req.json()
    payload = data.get("payload")
    if payload and payload.startswith("xtr_"):
        parts = payload.split("_")
        telegram_id = int(parts[1])
        amount = int(parts[2])
        users.update_one({"telegram_id": telegram_id}, {"$inc": {"balance.main": amount}}, upsert=True)
    return {"ok": True}

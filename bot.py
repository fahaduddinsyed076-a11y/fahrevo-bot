import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ── CONFIG ───────────────────────────────────────────────
BOT_TOKEN    = "8716616900:AAF96wyAR3JbhwlZFgaj1Vzv8ljGK8oY4qM"
SHEET_ID     = "1XM6fMZGlsA4lQoc1cdQz4w0EXk4Jdgk0I0dKkq5QWZA"
CREDS_FILE   = "credentials.json"
ALLOWED_USER = "syed_fahad076"
# ─────────────────────────────────────────────────────────

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

PERSONAL_CATEGORIES = {
    "food": "Food & Snacks", "chai": "Food & Snacks", "lunch": "Food & Snacks",
    "dinner": "Food & Snacks", "breakfast": "Food & Snacks", "snack": "Food & Snacks",
    "khana": "Food & Snacks", "wrap": "Food & Snacks", "frankie": "Food & Snacks",
    "auto": "Transport", "rapido": "Transport", "uber": "Transport",
    "ola": "Transport", "transport": "Transport", "bus": "Transport", "petrol": "Transport",
    "shop": "Shopping", "shopping": "Shopping", "clothes": "Shopping", "bag": "Shopping",
    "movie": "Entertainment", "game": "Entertainment", "cricket": "Entertainment",
    "netflix": "Entertainment", "outing": "Entertainment",
    "groceries": "Groceries", "grocery": "Groceries", "sabzi": "Groceries", "dmart": "Groceries",
    "recharge": "Mobile Recharge", "jio": "Mobile Recharge", "mobile": "Mobile Recharge",
    "medicine": "Medical", "doctor": "Medical", "medical": "Medical",
    "college": "Education", "books": "Education",
    "loan": "Loan", "emi": "Loan",
}

BUSINESS_CATEGORIES = {
    "chicken": "Raw Materials", "eggs": "Raw Materials", "bread": "Raw Materials",
    "masala": "Raw Materials", "sauce": "Raw Materials", "pista": "Raw Materials",
    "milk": "Raw Materials", "amul": "Raw Materials", "ingredients": "Raw Materials",
    "box": "Packaging", "boxes": "Packaging", "packaging": "Packaging", "tissue": "Packaging",
    "swiggy": "Delivery", "zomato": "Delivery", "delivery": "Delivery",
    "instagram": "Marketing", "boost": "Marketing", "marketing": "Marketing",
    "gas": "Utilities", "electricity": "Utilities",
    "equipment": "Equipment", "utensils": "Equipment",
}

HELP_MSG = """*Fahrevo Budget Bot* 🤖

*Personal expense:*
`chai 40 cash`
`auto 60 upi`
`lunch 120 upi`

*Business expense (add biz/cafe):*
`chicken 280 cash biz`
`packaging 350 upi cafe`
`milk 80 upi biz`

*Commands:*
/summary — today's total
/help — this message"""


def connect_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)


def find_next_empty_row(ws):
    """Find first empty row starting from row 3."""
    all_values = ws.get_all_values()
    for i in range(2, len(all_values)):  # index 2 = row 3
        if not any(all_values[i]):
            return i + 1  # 1-indexed
        # stop before TOTAL row
        if all_values[i] and "TOTAL" in str(all_values[i][0]).upper():
            return i  # insert before TOTAL
    return len(all_values) + 1


def parse_message(text: str):
    lower = text.lower().strip()
    parts = lower.split()

    is_business = any(k in parts for k in ["biz", "business", "cafe", "fahrevo"])

    payment = "UPI"
    for p in parts:
        if p in ["cash", "upi", "card", "gpay", "paytm", "phonepe", "online"]:
            payment = p.upper()
            break

    amount = None
    for p in parts:
        try:
            val = float(p)
            if val > 0:
                amount = val
                break
        except ValueError:
            continue

    if not amount:
        return None

    skip = {str(int(amount)), str(amount), payment.lower(),
            "biz", "business", "cafe", "fahrevo",
            "cash", "upi", "card", "gpay", "paytm", "phonepe", "online"}
    desc_parts = [p for p in parts if p not in skip]
    description = " ".join(desc_parts).title().strip() or "Expense"

    lookup = BUSINESS_CATEGORIES if is_business else PERSONAL_CATEGORIES
    category = "Miscellaneous" if is_business else "Other"
    for keyword, cat in lookup.items():
        if keyword in lower:
            category = cat
            break

    return {
        "is_business": is_business,
        "description": description,
        "amount": amount,
        "payment": payment,
        "category": category,
        "date": datetime.now().strftime("%d-%b-%Y"),
    }


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MSG, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MSG, parse_mode="Markdown")


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ALLOWED_USER:
        return
    try:
        sheet = connect_sheets()
        today = datetime.now().strftime("%d-%b-%Y")

        def sum_today(ws):
            rows = ws.get_all_values()
            total = 0.0
            for row in rows[2:]:
                if len(row) >= 3 and row[0] == today:
                    try:
                        total += float(str(row[2]).replace(",", "").replace("₹", "").strip())
                    except Exception:
                        pass
            return total

        p = sum_today(sheet.worksheet("Personal Expenses"))
        b = sum_today(sheet.worksheet("Fahrevo Cafe Expenses"))

        await update.message.reply_text(
            f"📊 *Today ({today})*\n\n"
            f"👤 Personal: *₹{p:.0f}*\n"
            f"☕ Cafe: *₹{b:.0f}*\n"
            f"──────────────\n"
            f"💰 *Total: ₹{p+b:.0f}*",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Summary error: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


async def handle_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ALLOWED_USER:
        await update.message.reply_text("⛔ Access denied.")
        return

    data = parse_message(update.message.text)
    if not data:
        await update.message.reply_text(
            "❌ Format not recognised.\n\nTry: `chai 40 cash` or `chicken 280 upi biz`\n\n/help for guide.",
            parse_mode="Markdown"
        )
        return

    try:
        sheet = connect_sheets()

        if data["is_business"]:
            ws = sheet.worksheet("Fahrevo Cafe Expenses")
            row = [data["date"], data["description"], data["amount"], data["payment"], ""]
        else:
            ws = sheet.worksheet("Personal Expenses")
            row = [data["date"], data["description"], data["amount"], data["payment"], ""]

        next_row = find_next_empty_row(ws)
        ws.insert_row(row, next_row, value_input_option="USER_ENTERED")

        emoji = "☕" if data["is_business"] else "👤"
        sheet_name = "Cafe Sheet" if data["is_business"] else "Personal Sheet"

        await update.message.reply_text(
            f"✅ *Added!*\n\n"
            f"{emoji} {sheet_name}\n"
            f"📝 {data['description']}\n"
            f"💰 ₹{data['amount']:.0f}\n"
            f"💳 {data['payment']}",
            parse_mode="Markdown"
        )
        logger.info(f"Added row {next_row}: {data}")

    except Exception as e:
        logger.error(f"Sheet error: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_expense))
    logger.info("✅ Fahrevo Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
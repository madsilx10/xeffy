import asyncio
import json
import os
import time
import hmac
import hashlib
import urllib.parse
from pyrogram import Client

# ── Config ──────────────────────────────────────────────
API_ID   = 0        # isi API ID lu
API_HASH = ""       # isi API Hash lu
BOT_USERNAME = "Xeffy_Bot"
ORG_SLUG = "xeffy"
CAMPAIGN_ID = "447eb124-e731-4853-be60-39aae9bb0127"
BASE_URL = "https://api.go.xeffy.io/api/mini"
DELAY_BETWEEN_ACCOUNTS = 10

# ── Load data ────────────────────────────────────────────
def load_file(path):
    with open(path, "r") as f:
        return [line.strip() for line in f if line.strip()]

# ── Generate Telegram initData ───────────────────────────
def generate_init_data(user_id, first_name, username, hash_token):
    """Generate Telegram Web App initData dari user info"""
    user_data = {
        "id": user_id,
        "first_name": first_name,
        "username": username,
        "language_code": "id",
        "allows_write_to_pm": True
    }
    user_json = json.dumps(user_data, separators=(',', ':'))
    auth_date = int(time.time())

    data_check = f"auth_date={auth_date}\nquery_id=AAFXCpV3AgAAAFcKlXfa-KYL\nuser={user_json}"
    secret_key = hmac.new("WebAppData".encode(), hash_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()

    init_data = urllib.parse.urlencode({
        "query_id": "AAFXCpV3AgAAAFcKlXfa-KYL",
        "user": user_json,
        "auth_date": auth_date,
        "hash": computed_hash
    })
    return init_data

# ── Xeffy API ────────────────────────────────────────────
import requests as req

def make_headers(session_token):
    return {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://tg.go.xeffy.io",
        "Referer": "https://tg.go.xeffy.io/",
        "Cookie": f"__Secure-xeffy_contrib.session_token={session_token}"
    }

def xeffy_login(init_data):
    r = req.post(
        f"{BASE_URL}/be-auth/sign-in/telegram",
        json={"initData": init_data, "orgSlug": ORG_SLUG},
        headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://tg.go.xeffy.io",
            "Referer": "https://tg.go.xeffy.io/",
        }
    )
    if r.status_code in [200, 201]:
        # Ambil session token dari Set-Cookie
        for cookie in r.cookies:
            if "session_token" in cookie.name:
                return cookie.value
    print(f"Login failed: {r.status_code} | {r.text[:100]}")
    return None

def check_in(session_token):
    r = req.post(
        f"{BASE_URL}/attendance",
        headers=make_headers(session_token)
    )
    return r.status_code in [200, 201]

def get_tasks(session_token):
    r = req.get(
        f"{BASE_URL}/campaigns/{CAMPAIGN_ID}/tasks",
        headers=make_headers(session_token)
    )
    if r.status_code == 200:
        return r.json().get("items", [])
    return []

def submit_task(session_token, task_id, proof=None):
    if proof is None:
        proof = {}
    r = req.post(
        f"{BASE_URL}/submissions",
        json={"taskId": task_id, "proof": proof},
        headers=make_headers(session_token)
    )
    return r.status_code in [200, 201]

# ── Core logic per akun ──────────────────────────────────
async def run_account(session_string, index):
    print(f"\n{'='*50}")
    print(f"[Akun {index}] Mulai...")

    async with Client(
        name=f"acc_{index}",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=session_string,
        in_memory=True
    ) as app:
        me = await app.get_me()
        print(f"[Akun {index}] @{me.username} ({me.id})")

        # Generate initData
        # Ambil bot token Xeffy dari WebApp (pakai placeholder, akan di-generate proper)
        # Untuk sekarang pakai method alternatif via request langsung
        init_data = generate_init_data(
            me.id,
            me.first_name or "",
            me.username or str(me.id),
            str(me.id)  # placeholder, perlu bot token asli
        )

    # Login ke Xeffy
    print(f"[Akun {index}] Login Xeffy...")
    session_token = xeffy_login(init_data)
    if not session_token:
        print(f"[Akun {index}] ❌ Login gagal")
        return

    print(f"[Akun {index}] ✅ Login berhasil")

    # Check in
    print(f"[Akun {index}] Check in...")
    ok = check_in(session_token)
    print(f"[Akun {index}] {'✅ Check in berhasil' if ok else '⚠️ Check in gagal/sudah'}")
    await asyncio.sleep(2)

    # Get tasks
    tasks = get_tasks(session_token)
    print(f"[Akun {index}] {len(tasks)} task ditemukan")

    # Submit semua task yang canSubmit
    for task in tasks:
        task_id = task.get("id")
        task_name = task.get("name", "unknown")
        task_kind = task.get("kind", "")
        can_submit = task.get("canSubmit", False)

        if not can_submit:
            print(f"[Akun {index}] Skip: {task_name} (sudah selesai)")
            continue

        # Skip quest Twitter/X
        if task_kind in ["twitter_follow", "twitter_reply", "twitter_retweet"]:
            print(f"[Akun {index}] Skip Twitter: {task_name}")
            continue

        # Quest quiz pakai quizSelectedIndex: 1
        if task_kind == "quiz":
            proof = {"quizSelectedIndex": 1}
        else:
            proof = {}

        ok = submit_task(session_token, task_id, proof)
        print(f"[Akun {index}] {'✅' if ok else '❌'} {task_name}")
        await asyncio.sleep(1)

    print(f"[Akun {index}] ✅ Selesai!")

# ── Menu ─────────────────────────────────────────────────
def print_menu(total):
    print("\n╔══════════════════════════════╗")
    print("║        XEFFY BOT             ║")
    print("╠══════════════════════════════╣")
    print(f"║  Total akun: {total:<17}║")
    print("╠══════════════════════════════╣")
    print("║  1. Jalanin semua akun       ║")
    print("║  2. Pilih satu akun          ║")
    print("║  3. From akun ke-N           ║")
    print("╚══════════════════════════════╝")

async def main():
    sessions = load_file("sessions.txt")
    total = len(sessions)
    print_menu(total)
    choice = input("\nPilih mode (1/2/3): ").strip()

    if choice == "1":
        indices = list(range(total))
    elif choice == "2":
        idx = int(input(f"Pilih akun (1-{total}): ")) - 1
        indices = [idx]
    elif choice == "3":
        start = int(input(f"Mulai dari akun ke- (1-{total}): ")) - 1
        indices = list(range(start, total))
    else:
        print("Pilihan tidak valid.")
        return

    for i in indices:
        await run_account(sessions[i], i + 1)
        if i != indices[-1]:
            print(f"\n⏳ Delay {DELAY_BETWEEN_ACCOUNTS} detik...")
            await asyncio.sleep(DELAY_BETWEEN_ACCOUNTS)

    print("\n✅ Semua akun selesai!")

if __name__ == "__main__":
    asyncio.run(main())

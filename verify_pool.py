import os, sys, time
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from DrissionPage import ChromiumPage, ChromiumOptions

print("=" * 60)
print("[*] AUTOMATIC HEALTH CHECK FOR ALL POOL TOKENS")
print("=" * 60)

with open("keys/accounts.txt", "r", encoding="utf-8") as f:
    lines = [l.strip() for l in f if l.strip()]

alive_accounts = []

co = ChromiumOptions()
co.auto_port()
co.set_argument("--window-position=-32000,-32000")
co.set_argument("--disable-blink-features=AutomationControlled")
co.set_argument("--no-sandbox")

for idx, line in enumerate(lines):
    parts = line.split(":")
    email = parts[0]
    pwd = parts[1] if len(parts) > 1 else ""
    sso = ":".join(parts[2:]) if len(parts) > 2 else ""
    
    if not sso:
        print(f"[{idx+1}/{len(lines)}] {email} -> NO SSO COOKIE -> DEAD")
        continue
        
    temp_dir = os.path.join(os.getcwd(), "temp_chrome", f"chk_{idx}")
    os.makedirs(temp_dir, exist_ok=True)
    co.set_argument(f"--user-data-dir={temp_dir}")
    
    page = ChromiumPage(co)
    try:
        page.get("https://grok.com", timeout=15)
        page.set.cookies({"name": "sso", "value": sso, "domain": ".grok.com", "path": "/"})
        page.set.cookies({"name": "sso-rw", "value": sso, "domain": ".grok.com", "path": "/"})
        page.get("https://grok.com", timeout=15)
        time.sleep(2)
        
        curr_url = (page.url or "").lower()
        has_signin = page.ele("text:Sign In") or page.ele("text:Log in")
        has_textarea = page.ele("tag:textarea") or page.ele("@placeholder*Ask") or page.ele(".ProseMirror")
        
        if "signin" in curr_url or "login" in curr_url or has_signin or not has_textarea:
            print(f"[{idx+1}/{len(lines)}] ❌ {email} -> SESSION EXPIRED / DEAD")
        else:
            print(f"[{idx+1}/{len(lines)}] ✅ {email} -> ALIVE & HEALTHY!")
            alive_accounts.append(line)
    except Exception as e:
        print(f"[{idx+1}/{len(lines)}] ❌ {email} -> Error: {e}")
    finally:
        page.quit()
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

print("\n" + "=" * 60)
print(f"Summary: {len(alive_accounts)} / {len(lines)} accounts are ALIVE")
print("=" * 60)

# Save only alive accounts
if alive_accounts:
    with open("keys/accounts.txt", "w", encoding="utf-8") as f:
        for a in alive_accounts:
            f.write(a + "\n")
    with open("keys/grok.txt", "w", encoding="utf-8") as f:
        for a in alive_accounts:
            f.write(":".join(a.split(":")[2:]) + "\n")
    print("✅ Successfully pruned dead accounts from keys/accounts.txt and keys/grok.txt")

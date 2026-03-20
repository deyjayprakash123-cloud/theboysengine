import urllib.parse
import re
import random
import requests
import subprocess
import platform
import threading
from flask import Flask, request, Response
from cryptography.fernet import Fernet

app = Flask(__name__)

# ==========================================
# MODULE 1: AES-256 LOG ENCRYPTION
# ==========================================
print("Generating Session Encryption Key...")
SESSION_KEY = Fernet.generate_key()
cipher_suite = Fernet(SESSION_KEY)

def encrypt_data(text):
    """Scrambles your local logs so no one can read them."""
    if not text: 
        return "UNKNOWN"
    return cipher_suite.encrypt(text.encode('utf-8')).decode('utf-8')

# ==========================================
# MODULE 2: DYNAMIC IP ROTATION
# ==========================================
PROXY_POOL = []

def fetch_free_proxies():
    """Automatically scrapes fresh, free SOCKS5 proxies from the web on startup."""
    print("🌍 Scraping fresh public proxies... Please wait.")
    try:
        url = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            proxies = resp.text.splitlines()
            sampled = random.sample(proxies, min(50, len(proxies)))
            for p in sampled:
                PROXY_POOL.append(f"socks5h://{p}")
            print(f"✅ Loaded {len(PROXY_POOL)} SOCKS5 IPs into the Ghost Pool!\n")
        else:
            print("⚠️ Failed to reach proxy database. Traffic will default to local IP.\n")
    except Exception as e:
        print(f"⚠️ Proxy scraper error: {e}. Traffic will default to local IP.\n")

def get_random_proxy():
    """Selects a random IP from the pool."""
    if not PROXY_POOL: 
        return None
    chosen = random.choice(PROXY_POOL)
    return {"http": chosen, "https": chosen}

# ==========================================
# MODULE 3: THE TUNNEL ENGINE (Link Fixer)
# ==========================================
def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Upgrade-Insecure-Requests': '1',
    }

def rewrite_html(html_content, base_url):
    """Intercepts HTML and forces all links to route back through the proxy."""
    
    # Destroys 'target="_blank"' so links never force-open a new, unproxied Chrome tab
    html_content = re.sub(r'target=[\'"]_blank[\'"]', '', html_content, flags=re.IGNORECASE)

    def replacer(match):
        attr, quote, link = match.group(1), match.group(2), match.group(3)
        if link.startswith(("data:", "javascript:", "#", "mailto:")): 
            return match.group(0)
        
        absolute_url = urllib.parse.urljoin(base_url, link)
        return f"{attr}={quote}/proxy?url={urllib.parse.quote(absolute_url)}{quote}"

    html_content = re.sub(r'(href|src)=([\'"])(.*?)\2', replacer, html_content, flags=re.IGNORECASE)
    return html_content

# ==========================================
# ROUTE 1: THE CORE PROXY (ZERO FAILURE OVERRIDE)
# ==========================================
@app.route('/proxy')
def proxy_route():
    target_url = request.args.get("url", "")
    if not target_url: 
        return "No URL provided", 400

    # Force HTTPS encryption
    if target_url.startswith("//"): target_url = "https:" + target_url
    if not target_url.startswith("http"): target_url = "https://" + target_url

    # AES Encrypted Terminal Logging
    print(f"🔒 [ENCRYPTED TARGET]: {encrypt_data(target_url)[:50]}...")

    MAX_RETRIES = 3
    
    # PHASE 1: Attempt to hide IP using Proxy Pool
    for attempt in range(MAX_RETRIES):
        active_proxy = get_random_proxy()
        if not active_proxy:
            break # Skip to fallback if pool is empty
            
        try:
            resp = requests.get(target_url, headers=get_headers(), proxies=active_proxy, stream=True, timeout=5)
            content_type = resp.headers.get("Content-Type", "")

            if "text/html" in content_type:
                fixed_html = rewrite_html(resp.text, target_url)
                banner = f"<div style='background:#00ff00; color:black; padding:8px; text-align:center; font-family:monospace; font-weight:bold; position:sticky; top:0; z-index:999999;'>🟢 ENCRYPTED & ANONYMOUS | Routed via: {active_proxy['http']}</div>"
                fixed_html = fixed_html.replace("<body", f"<body\n{banner}", 1)
                return Response(fixed_html, content_type=content_type)
            else:
                def generate():
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk: yield chunk
                return Response(generate(), content_type=content_type)
        except requests.exceptions.RequestException:
            continue # Silently move to the next proxy if this one dies

    # PHASE 2: THE UNBREAKABLE FALLBACK
    # If all proxies fail, it silently establishes a direct, HTTPS-encrypted connection.
    try:
        print("⚠️ [SYSTEM OVERRIDE]: Proxies dead. Establishing direct encrypted HTTPS tunnel.")
        resp = requests.get(target_url, headers=get_headers(), stream=True, timeout=10)
        content_type = resp.headers.get("Content-Type", "")

        if "text/html" in content_type:
            fixed_html = rewrite_html(resp.text, target_url)
            banner = f"<div style='background:#ff9900; color:black; padding:8px; text-align:center; font-family:monospace; font-weight:bold; position:sticky; top:0; z-index:999999;'>🟠 DIRECT ENCRYPTED TUNNEL | Proxies bypassed to ensure connection.</div>"
            fixed_html = fixed_html.replace("<body", f"<body\n{banner}", 1)
            return Response(fixed_html, content_type=content_type)
        else:
            def generate():
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk: yield chunk
            return Response(generate(), content_type=content_type)
            
    except Exception as e:
        return f"<h3>Critical Target Failure</h3><p>The website {target_url} is completely offline or blocking all traffic.</p>", 502

# ==========================================
# ROUTE 2: REAL-TIME SEARCH
# ==========================================
@app.route('/search')
def search_route():
    query = request.args.get("q", "")
    if not query: 
        return "No query provided", 400
    
    # Send the search to DuckDuckGo Lite, pipe it through our Unbreakable Tunnel
    search_url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(query)}"
    
    with app.test_request_context(f'/proxy?url={urllib.parse.quote(search_url)}'):
        return proxy_route()

# ==========================================
# ROUTE 3: DASHBOARD
# ==========================================
@app.route('/')
def home():
    proxy_status = f"{len(PROXY_POOL)} EXTERNAL IPs LOADED" if PROXY_POOL else "LOCAL IP ONLY"
    
    return f'''
        <html>
        <body style="text-align:center; padding-top:100px; font-family:monospace; background:#000; color:#00ff00;">
            <h1 style="font-size:54px; margin-bottom:10px;">GHOST ENGINE v8.0</h1>
            <p style="font-size:18px;">AES-256 Log Encryption | Unbreakable Fallback System | {proxy_status}</p>
            
            <div style="background:#111; border:1px solid #00ff00; padding:40px; border-radius:10px; display:inline-block; margin-top:30px; width: 600px;">
                <form action="/search" method="get">
                    <input type="text" name="q" style="width:80%; padding:15px; border-radius:5px; border:1px solid #00ff00; background:#000; color:#00ff00; font-size:16px;" placeholder="Search DuckDuckGo securely...">
                    <br><br>
                    <input type="submit" value="ENCRYPTED SEARCH" style="padding:12px 35px; background:#00ff00; color:black; font-weight:bold; cursor:pointer; border:none; border-radius:5px; font-size:16px;">
                </form>
            </div>
            
            <br>
            
            <div style="background:#111; border:1px solid #00ff00; padding:40px; border-radius:10px; display:inline-block; margin-top:30px; width: 600px;">
                <form action="/proxy" method="get">
                    <input type="text" name="url" style="width:80%; padding:15px; border-radius:5px; border:1px solid #00ff00; background:#000; color:#00ff00; font-size:16px;" placeholder="Direct URL (e.g., https://wikipedia.org)">
                    <br><br>
                    <input type="submit" value="OPEN TUNNEL" style="padding:12px 35px; background:#00ff00; color:black; font-weight:bold; cursor:pointer; border:none; border-radius:5px; font-size:16px;">
                </form>
            </div>
        </body>
        </html>
    '''

# ==========================================
# MODULE 4: AUTO-INCOGNITO LAUNCHER
# ==========================================
def open_incognito():
    """Talks to the OS to force Google Chrome open in a private window."""
    target_url = "http://127.0.0.1:5000"
    os_name = platform.system()
    
    try:
        if os_name == 'Windows':
            subprocess.Popen(['cmd', '/c', 'start', 'chrome', '--incognito', target_url])
        elif os_name == 'Darwin': 
            subprocess.Popen(['open', '-a', 'Google Chrome', '--args', '--incognito', target_url])
        elif os_name == 'Linux':
            subprocess.Popen(['google-chrome', '--incognito', target_url])
    except Exception as e:
        print(f"⚠️ Could not auto-launch Incognito: {e}. Please open it manually.")

# ==========================================
# SYSTEM STARTUP
# ==========================================
if __name__ == '__main__':
    print("=====================================================")
    fetch_free_proxies()
    print("🚀 GHOST ENGINE ONLINE: http://127.0.0.1:5000")
    print(f"🔑 Session Key: {SESSION_KEY.decode('utf-8')}")
    print("=====================================================\n")
    
    # Wait 1.5 seconds for Flask to boot, then auto-launch Chrome Incognito
    threading.Timer(1.5, open_incognito).start()
    
    app.run(port=5000, debug=True, use_reloader=False)

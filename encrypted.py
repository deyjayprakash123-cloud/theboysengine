import urllib.parse
import re
import random
import requests
from flask import Flask, request, Response
from cryptography.fernet import Fernet

app = Flask(__name__)

# ==========================================
# 1. AES-256 LOG ENCRYPTION
# ==========================================
print("Generating Session Encryption Key...")
SESSION_KEY = Fernet.generate_key()
cipher_suite = Fernet(SESSION_KEY)

def encrypt_data(text):
    """Scrambles your local logs so no one can read them."""
    if not text: return "UNKNOWN"
    return cipher_suite.encrypt(text.encode('utf-8')).decode('utf-8')

# ==========================================
# 2. DYNAMIC IP ROTATION (The Auto-Scraper)
# ==========================================
PROXY_POOL = []

def fetch_free_proxies():
    """Automatically scrapes fresh, free proxies from the web on startup."""
    print("🌍 Scraping fresh public proxies... Please wait.")
    try:
        # Pulling from a well-known, constantly updated free proxy GitHub repository
        url = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            proxies = resp.text.splitlines()
            # Grab a random sample of 50 proxies so we don't overload the system
            sampled = random.sample(proxies, min(50, len(proxies)))
            for p in sampled:
                PROXY_POOL.append(f"http://{p}")
            print(f"✅ Successfully loaded {len(PROXY_POOL)} global IPs into the Ghost Pool!\n")
        else:
            print("⚠️ Failed to reach proxy database. Traffic will use your local IP.\n")
    except Exception as e:
        print(f"⚠️ Proxy scraper error: {e}. Traffic will use your local IP.\n")

def get_random_proxy():
    """Selects a random IP from the pool to route your request through."""
    if not PROXY_POOL: return None
    chosen = random.choice(PROXY_POOL)
    return {"http": chosen, "https": chosen}

# ==========================================
# 3. THE TUNNEL ENGINE (Link Fixer)
# ==========================================
def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Upgrade-Insecure-Requests': '1',
    }

def rewrite_html(html_content, base_url):
    def replacer(match):
        attr, quote, link = match.group(1), match.group(2), match.group(3)
        if link.startswith(("data:", "javascript:", "#", "mailto:")): return match.group(0)
        absolute_url = urllib.parse.urljoin(base_url, link)
        return f"{attr}={quote}/proxy?url={urllib.parse.quote(absolute_url)}{quote}"

    html_content = re.sub(r'(href|src)=([\'"])(.*?)\2', replacer, html_content, flags=re.IGNORECASE)
    return html_content

# ==========================================
# ROUTE 1: THE CORE PROXY
# ==========================================
@app.route('/proxy')
def proxy_route():
    target_url = request.args.get("url", "")
    if not target_url: return "No URL provided", 400

    if target_url.startswith("//"): target_url = "https:" + target_url
    if not target_url.startswith("http"): target_url = "https://" + target_url

    # AES ENCRYPTION: Secure your local logs
    client_ip = request.remote_addr
    print(f"🔒 [ENCRYPTED LOG] Target: {encrypt_data(target_url)[:50]}...")

    # Grab a random IP
    active_proxy = get_random_proxy()
    proxy_display = active_proxy['http'] if active_proxy else "LOCAL IP"

    try:
        # A 10-second timeout prevents the app from freezing if it picks a dead proxy
        resp = requests.get(target_url, headers=get_headers(), proxies=active_proxy, stream=True, timeout=10)
        content_type = resp.headers.get("Content-Type", "")

        if "text/html" in content_type:
            fixed_html = rewrite_html(resp.text, target_url)
            banner = f"<div style='background:#00ff00; color:black; padding:8px; text-align:center; font-family:monospace; font-weight:bold; position:sticky; top:0; z-index:999999;'>🟢 GHOST ENGINE ACTIVE | Routed via: {proxy_display}</div>"
            fixed_html = fixed_html.replace("<body", f"<body\n{banner}", 1)
            return Response(fixed_html, content_type=content_type)
            
        else:
            def generate():
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk: yield chunk
            return Response(generate(), content_type=content_type)

    except requests.exceptions.RequestException:
        # If the free proxy is dead, show an error and tell the user to try again
        error_html = f"""
        <body style='background:#111; color:#00ff00; font-family:monospace; text-align:center; padding-top:100px;'>
            <h2>⚠️ Connection Failed</h2>
            <p>The randomized proxy ({proxy_display}) was too slow or went offline.</p>
            <p>This is normal for free public proxies.</p>
            <button onclick='window.location.reload();' style='padding:10px 20px; background:#00ff00; color:black; border:none; cursor:pointer; font-weight:bold;'>↻ Refresh to try a new IP</button>
        </body>
        """
        return Response(error_html, status=502)

# ==========================================
# ROUTE 2: REAL-TIME SEARCH
# ==========================================
@app.route('/search')
def search_route():
    query = request.args.get("q", "")
    if not query: return "No query provided", 400
    search_url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(query)}"
    
    with app.test_request_context(f'/proxy?url={urllib.parse.quote(search_url)}'):
        return proxy_route()

# ==========================================
# ROUTE 3: DASHBOARD
# ==========================================
@app.route('/')
def home():
    proxy_status = f"ROTATING {len(PROXY_POOL)} EXTERNAL IPs" if PROXY_POOL else "LOCAL IP ONLY (Fetch Failed)"
    proxy_color = "#00ff00" if PROXY_POOL else "#ff3333"
    
    return f'''
        <html>
        <body style="text-align:center; padding-top:100px; font-family:monospace; background:#000; color:#00ff00;">
            <h1 style="font-size:54px; margin-bottom:10px;">GHOST ENGINE v4.0</h1>
            <p style="font-size:18px;">AES-256 Encrypted Logs | <span style="color:{proxy_color}; font-weight:bold;">{proxy_status}</span></p>
            
            <div style="background:#111; border:1px solid #00ff00; padding:40px; border-radius:10px; display:inline-block; margin-top:30px; width: 600px;">
                <form action="/search" method="get">
                    <input type="text" name="q" style="width:80%; padding:15px; border-radius:5px; border:1px solid #00ff00; background:#000; color:#00ff00; font-size:16px;" placeholder="Search the web securely...">
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

if __name__ == '__main__':
    print("=====================================================")
    # Fire up the auto-scraper before starting the server!
    fetch_free_proxies()
    print("🚀 GHOST ENGINE ONLINE: http://127.0.0.1:5000")
    print(f"🔑 Session Key: {SESSION_KEY.decode('utf-8')}")
    print("=====================================================\n")
    app.run(port=5000, debug=True, use_reloader=False)import urllib.parse
import re
import random
import requests
from flask import Flask, request, Response
from cryptography.fernet import Fernet

app = Flask(__name__)

# ==========================================
# 1. AES-256 LOG ENCRYPTION
# ==========================================
print("Generating Session Encryption Key...")
SESSION_KEY = Fernet.generate_key()
cipher_suite = Fernet(SESSION_KEY)

def encrypt_data(text):
    """Scrambles your local logs so no one can read them."""
    if not text: return "UNKNOWN"
    return cipher_suite.encrypt(text.encode('utf-8')).decode('utf-8')

# ==========================================
# 2. DYNAMIC IP ROTATION (The Auto-Scraper)
# ==========================================
PROXY_POOL = []

def fetch_free_proxies():
    """Automatically scrapes fresh, free proxies from the web on startup."""
    print("🌍 Scraping fresh public proxies... Please wait.")
    try:
        # Pulling from a well-known, constantly updated free proxy GitHub repository
        url = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            proxies = resp.text.splitlines()
            # Grab a random sample of 50 proxies so we don't overload the system
            sampled = random.sample(proxies, min(50, len(proxies)))
            for p in sampled:
                PROXY_POOL.append(f"http://{p}")
            print(f"✅ Successfully loaded {len(PROXY_POOL)} global IPs into the Ghost Pool!\n")
        else:
            print("⚠️ Failed to reach proxy database. Traffic will use your local IP.\n")
    except Exception as e:
        print(f"⚠️ Proxy scraper error: {e}. Traffic will use your local IP.\n")

def get_random_proxy():
    """Selects a random IP from the pool to route your request through."""
    if not PROXY_POOL: return None
    chosen = random.choice(PROXY_POOL)
    return {"http": chosen, "https": chosen}

# ==========================================
# 3. THE TUNNEL ENGINE (Link Fixer)
# ==========================================
def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Upgrade-Insecure-Requests': '1',
    }

def rewrite_html(html_content, base_url):
    def replacer(match):
        attr, quote, link = match.group(1), match.group(2), match.group(3)
        if link.startswith(("data:", "javascript:", "#", "mailto:")): return match.group(0)
        absolute_url = urllib.parse.urljoin(base_url, link)
        return f"{attr}={quote}/proxy?url={urllib.parse.quote(absolute_url)}{quote}"

    html_content = re.sub(r'(href|src)=([\'"])(.*?)\2', replacer, html_content, flags=re.IGNORECASE)
    return html_content

# ==========================================
# ROUTE 1: THE CORE PROXY
# ==========================================
@app.route('/proxy')
def proxy_route():
    target_url = request.args.get("url", "")
    if not target_url: return "No URL provided", 400

    if target_url.startswith("//"): target_url = "https:" + target_url
    if not target_url.startswith("http"): target_url = "https://" + target_url

    # AES ENCRYPTION: Secure your local logs
    client_ip = request.remote_addr
    print(f"🔒 [ENCRYPTED LOG] Target: {encrypt_data(target_url)[:50]}...")

    # Grab a random IP
    active_proxy = get_random_proxy()
    proxy_display = active_proxy['http'] if active_proxy else "LOCAL IP"

    try:
        # A 10-second timeout prevents the app from freezing if it picks a dead proxy
        resp = requests.get(target_url, headers=get_headers(), proxies=active_proxy, stream=True, timeout=10)
        content_type = resp.headers.get("Content-Type", "")

        if "text/html" in content_type:
            fixed_html = rewrite_html(resp.text, target_url)
            banner = f"<div style='background:#00ff00; color:black; padding:8px; text-align:center; font-family:monospace; font-weight:bold; position:sticky; top:0; z-index:999999;'>🟢 GHOST ENGINE ACTIVE | Routed via: {proxy_display}</div>"
            fixed_html = fixed_html.replace("<body", f"<body\n{banner}", 1)
            return Response(fixed_html, content_type=content_type)
            
        else:
            def generate():
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk: yield chunk
            return Response(generate(), content_type=content_type)

    except requests.exceptions.RequestException:
        # If the free proxy is dead, show an error and tell the user to try again
        error_html = f"""
        <body style='background:#111; color:#00ff00; font-family:monospace; text-align:center; padding-top:100px;'>
            <h2>⚠️ Connection Failed</h2>
            <p>The randomized proxy ({proxy_display}) was too slow or went offline.</p>
            <p>This is normal for free public proxies.</p>
            <button onclick='window.location.reload();' style='padding:10px 20px; background:#00ff00; color:black; border:none; cursor:pointer; font-weight:bold;'>↻ Refresh to try a new IP</button>
        </body>
        """
        return Response(error_html, status=502)

# ==========================================
# ROUTE 2: REAL-TIME SEARCH
# ==========================================
@app.route('/search')
def search_route():
    query = request.args.get("q", "")
    if not query: return "No query provided", 400
    search_url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(query)}"
    
    with app.test_request_context(f'/proxy?url={urllib.parse.quote(search_url)}'):
        return proxy_route()

# ==========================================
# ROUTE 3: DASHBOARD
# ==========================================
@app.route('/')
def home():
    proxy_status = f"ROTATING {len(PROXY_POOL)} EXTERNAL IPs" if PROXY_POOL else "LOCAL IP ONLY (Fetch Failed)"
    proxy_color = "#00ff00" if PROXY_POOL else "#ff3333"
    
    return f'''
        <html>
        <body style="text-align:center; padding-top:100px; font-family:monospace; background:#000; color:#00ff00;">
            <h1 style="font-size:54px; margin-bottom:10px;">GHOST ENGINE v4.0</h1>
            <p style="font-size:18px;">AES-256 Encrypted Logs | <span style="color:{proxy_color}; font-weight:bold;">{proxy_status}</span></p>
            
            <div style="background:#111; border:1px solid #00ff00; padding:40px; border-radius:10px; display:inline-block; margin-top:30px; width: 600px;">
                <form action="/search" method="get">
                    <input type="text" name="q" style="width:80%; padding:15px; border-radius:5px; border:1px solid #00ff00; background:#000; color:#00ff00; font-size:16px;" placeholder="Search the web securely...">
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

if __name__ == '__main__':
    print("=====================================================")
    # Fire up the auto-scraper before starting the server!
    fetch_free_proxies()
    print("🚀 GHOST ENGINE ONLINE: http://127.0.0.1:5000")
    print(f"🔑 Session Key: {SESSION_KEY.decode('utf-8')}")
    print("=====================================================\n")
    app.run(port=5000, debug=True, use_reloader=False)

# License : GPLv2.0
# copyright (c) 2023  Dave Bailey
# Author: Dave Bailey (dbisu, @daveisu)
# FeatherS2 board support

import socketpool
import time
import os
import storage

import wsgiserver as server
from adafruit_wsgi.wsgi_app import WSGIApp
import wifi

from duckyinpython import *

payload_html = """<html>
    <head>
        <title>Pico W Ducky</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>button{{margin:0.2em}}html{{font-family:'Open Sans', sans-serif;margin:2%}}table{{width:30%;max-width:20vh;margin-bottom:1em;border-collapse:collapse}}</style>
    </head>
    <body>
        <h1>Pico W Ducky</h1>
        <table border="1"><tr><th>Payload</th><th>Actions</th></tr>{}</table><br>
        <a href="/new"><button>New Script</button></a>
    </body>
</html>
"""

edit_html = """<!DOCTYPE html>
<html>
    <head>
        <title>Script Editor</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>button{{margin-top:1em}}.main{{font-family:'Open Sans', sans-serif;margin:2%}}textarea{{width:100%;max-width:80vh;margin-bottom:1em;height:50vh}}</style>
    </head>
    <body>
        <form action="/write/{}" method="POST">
            <textarea rows="5" name="scriptData">{}</textarea><br/>
            <input type="submit" value="Submit"/>
        </form>
        <br>
        <a href="/ducky"><button>Home</button></a>
    </body>
</html>
"""

new_html = """<!DOCTYPE html>
<html>
    <head>
        <title>New Script</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>button{margin-top:1em}.main{font-family:'Open Sans', sans-serif;margin:2%}textarea{width:100%;max-width:80vh;margin-bottom:1em}#ducky-input{height:50vh}</style>
    </head>
    <body>
        <div class="main">
            <form action="/new" method="POST">
                <p>New Script:</p>
                <textarea rows="1" name="scriptName" placeholder="script name"></textarea><br>
                <textarea id="ducky-input" rows="5" name="scriptData" placeholder="script"></textarea>
                <br><input type="submit" value="Submit"/>
            </form>
            <a href="/ducky"><button>Go Back</button></a>
        </div>
    </body>
</html>
"""

newrow_html = "<tr><td>{}</td><td><a href='/edit/{}'><button>Edit</button></a><a href='/run/{}'><button>Run</button></a></tr>"

def setPayload(payload_number):
    if payload_number == 1:
        payload = "payload.dd"
    else:
        payload = "payload" + str(payload_number) + ".dd"
    return payload

def ducky_main(request):
    print("Ducky main")
    payloads = []
    rows = ""
    files = os.listdir()
    for f in files:
        if '.dd' in f:
            payloads.append(f)
            newrow = newrow_html.format(f, f, f)
            rows = rows + newrow
    response = payload_html.format(rows)
    return response

def cleanup_text(buffer):
    # Mapping table for specific encoded strings
    replacements = {
        '%3A': ':',
        '%2F': '/',
        '%7C': '|',
        '%0D%0A': '\n',  # Windows-style newlines
        '%20': ' ',       # Space
        '+': ' '          # Replace '+' with space
    }
    
    # Replace each encoded string with its corresponding character
    for encoded, actual in replacements.items():
        buffer = buffer.replace(encoded, actual)
    
    return buffer + '\n'

web_app = WSGIApp()

@web_app.route("/ducky")
def duck_main(request):
    response = ducky_main(request)
    return ("200 OK", [('Content-Type', 'text/html')], response)

@web_app.route("/edit/<filename>")
def edit(request, filename):
    print("Editing", filename)
    try:
        with open(filename, "r", encoding='utf-8') as f:
            textbuffer = f.read()
    except FileNotFoundError:
        return ("404 Not Found", [('Content-Type', 'text/html')], "<html><body>File not found</body></html>")

    response = edit_html.format(filename, textbuffer)
    return ("200 OK", [('Content-Type', 'text/html')], response)

@web_app.route("/write/<filename>", methods=["POST"])
def write_script(request, filename):
    data = request.body.getvalue()
    fields = data.split("&")
    form_data = {}
    for field in fields:
        key, value = field.split('=')
        form_data[key] = value

    storage.remount("/", readonly=False)
    with open(filename, "w", encoding='utf-8') as f:
        textbuffer = cleanup_text(form_data['scriptData'])
        f.write(textbuffer)
    storage.remount("/", readonly=True)
    # Redirect directly to home page
    return ("302 Found", [
        ("Location", "/ducky"),
        ("Content-Type", "text/html")
    ], "<html><body>Redirecting...</body></html>")

@web_app.route("/new", methods=['GET', 'POST'])
def write_new_script(request):
    response = ''
    if request.method == 'GET':
        response = new_html
    else:
        data = request.body.getvalue()
        fields = data.split("&")
        form_data = {}
        for field in fields:
            key, value = field.split('=')
            form_data[key] = value

        filename = form_data['scriptName']
        textbuffer = cleanup_text(form_data['scriptData'])
        storage.remount("/", readonly=False)
        with open(filename, "w", encoding='utf-8') as f:
            f.write(textbuffer)
        storage.remount("/", readonly=True)
        # Redirect directly to home page
        return ("302 Found", [
            ("Location", "/ducky"),
            ("Content-Type", "text/html")
        ], "<html><body>Redirecting...</body></html>")
    return ("200 OK", [('Content-Type', 'text/html')], response)

@web_app.route("/run/<filename>")
def run_script(request, filename):
    print("run_script", filename)
    try:
        runScript(filename)
    except Exception as e:
        return ("500 Internal Server Error", [('Content-Type', 'text/html')], f"<html><body>Error: {e}</body></html>")
    return ("302 Found", [
        ("Location", "/ducky"),
        ("Content-Type", "text/html")
    ], "<html><body>Redirecting...</body></html>")

@web_app.route("/")
def index(request):
    response = ducky_main(request)
    return ("200 OK", [('Content-Type', 'text/html')], response)

@web_app.route("/api/run/<filenumber>")
def api_run_script(request, filenumber):
    filename = setPayload(int(filenumber))
    print("run_script", filenumber)
    try:
        runScript(filename)
    except Exception as e:
        return ("500 Internal Server Error", [('Content-Type', 'text/html')], f"<html><body>Error: {e}</body></html>")
    return ("200 OK", [('Content-Type', 'text/html')], "<html><body>Script executed successfully</body></html>")

async def startWebService():
    HOST = repr(wifi.radio.ipv4_address_ap)
    PORT = 80
    print(HOST, PORT)

    wsgiServer = server.WSGIServer(80, application=web_app)
    print(f"Open this IP in your browser: http://{HOST}:{PORT}/")

    wsgiServer.start()
    while True:
        wsgiServer.update_poll()
        await asyncio.sleep(0)


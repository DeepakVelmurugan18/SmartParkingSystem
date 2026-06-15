import os
import glob
import re

js_files = glob.glob('static/js/*.js')

for js_file in js_files:
    with open(js_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We want to find: socket.on('EVENT_NAME', (data) => {
    # And replace with: socket.on('EVENT_NAME', (data) => {
    # if (data && data.server_timestamp) fetch('/api/log-latency', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({event:'EVENT_NAME', latency:Date.now()-data.server_timestamp})});
    
    def replacer(match):
        event_name = match.group(1)
        data_var = match.group(2)
        original = match.group(0)
        
        # Don't add if already added
        if "fetch('/api/log-latency'" in original:
            return original
            
        latency_code = f"\n        if ({data_var} && {data_var}.server_timestamp) fetch('/api/log-latency', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{event:'{event_name}', latency:Date.now()-{data_var}.server_timestamp}})}});"
        return original + latency_code

    # Regex to match socket.on('...', (data) => { or socket.on("...", function(data) {
    new_content = re.sub(r"socket\.on\(['\"]([^'\"]+)['\"],\s*(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>\s*\{", replacer, content)
    new_content = re.sub(r"socket\.on\(['\"]([^'\"]+)['\"],\s*function\s*\(([^)]*)\)\s*\{", replacer, new_content)
    
    # Also fix cases where there is no data parameter e.g. socket.on('event', () => {
    def replacer_no_args(match):
        event_name = match.group(1)
        original = match.group(0)
        if "fetch('/api/log-latency'" in original: return original
        # If no data is passed, we can't measure latency this way easily without changing the sender to send data.
        return original
        
    new_content = re.sub(r"socket\.on\(['\"]([^'\"]+)['\"],\s*\(\)\s*=>\s*\{", replacer_no_args, new_content)

    with open(js_file, 'w', encoding='utf-8') as f:
        f.write(new_content)

print("Latency logging injected into all JS files.")

import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app

rule_paths = set(rule.rule for rule in app.url_map.iter_rules())
template_dir = 'templates'
broken_hrefs = []

for root, _, files in os.walk(template_dir):
    for f in files:
        if f.endswith('.html'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as tf:
                content = tf.read()
            # find hardcoded href="/path" (not template tags)
            matches = re.findall(r'href="(/[a-zA-Z0-9_\-\/]+)"', content)
            for href in matches:
                # remove params or wildcards if any
                base_href = href.split('?')[0]
                # Check if matches any rule
                matched = False
                for r in rule_paths:
                    # check if base_href matches rule (accounting for <int:...>)
                    pattern = re.sub(r'<[a-zA-Z_:]+>', r'[^/]+', r)
                    if re.fullmatch(pattern, base_href):
                        matched = True
                        break
                if not matched and not base_href.startswith('/static'):
                    broken_hrefs.append((f, href))

print(f"Hardcoded broken hrefs: {broken_hrefs}")

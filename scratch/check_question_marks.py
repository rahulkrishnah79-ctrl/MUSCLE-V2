import glob
import re

for f in glob.glob('*.py') + glob.glob('api/*.py'):
    with open(f, encoding='utf-8') as fp:
        for idx, line in enumerate(fp, 1):
            if '?' in line and not line.strip().startswith('#'):
                # find string literals in line containing ?
                literals = re.findall(r"['\"][^'\"]*\?[^'\"]*['\"]", line)
                if literals:
                    print(f"{f}:{idx} -> literals: {literals} in {line.strip()[:80]}")

#!/usr/local/bin/python
import os
import sys
import re
from uvicorn.main import main

if __name__ == '__main__':
    # Intercept any unexpanded ${PORT...} shell variables or invalid non-digit ports
    for i, arg in enumerate(sys.argv):
        if arg == '--port' and i + 1 < len(sys.argv):
            val = sys.argv[i + 1]
            if not val.isdigit():
                real_port = os.environ.get('PORT', '8000').strip()
                if not real_port.isdigit():
                    real_port = '8000'
                print(f"[*] Intercepted non-integer port argument '{val}', resolved to: {real_port}")
                sys.argv[i + 1] = real_port

    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(main())

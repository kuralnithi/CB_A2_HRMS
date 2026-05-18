import glob
import re

base = r'c:/Users/kural/Downloads/capstone_project_assignments/ai_hr_copilot/frontend'
files = glob.glob(base + '/app/dashboard/**/*.tsx', recursive=True)
files.append(base + '/app/dashboard/page.tsx')

for fp in files:
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            c = f.read()
        # Fix: NEXT_PUBLIC_API_URL already includes /api/v1
        # So remove duplicate /api/v1 from the appended path
        # Pattern: ${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/api/v1/XXXXX
        # Replace with: ${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1"}/XXXXX
        old_fallback = 'http://127.0.0.1:8000"}/api/v1/'
        new_fallback = 'http://127.0.0.1:8000/api/v1"}/'
        if old_fallback in c:
            nc = c.replace(old_fallback, new_fallback)
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(nc)
            print('Fixed:', fp)
    except Exception as e:
        print('Error:', fp, e)

print('Done!')

import re

with open('tests/test_retention.py', 'r') as f:
    content = f.read()

# Replace time_is_pct with original_time_is_pct in test data
content = content.replace('"time_is_pct": True', '"original_time_is_pct": True')
content = content.replace('"time_is_pct": False', '"original_time_is_pct": False')

with open('tests/test_retention.py', 'w') as f:
    f.write(content)

print("Fixed test file!")
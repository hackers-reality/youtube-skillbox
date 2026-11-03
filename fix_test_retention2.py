import re

with open('tests/test_retention.py', 'r') as f:
    content = f.read()

# Replace time_is_pct with original_time_is_pct in test assertions
content = content.replace('points[0].get("time_is_pct", False)', 'points[0].get("original_time_is_pct", False)')
content = content.replace('points[0].get("time_is_pct", True)', 'points[0].get("original_time_is_pct", True)')

with open('tests/test_retention.py', 'w') as f:
    f.write(content)

print("Fixed test file!")
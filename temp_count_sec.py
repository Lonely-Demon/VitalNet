import json

with open('docs/security-audits/2026-03-red-team/BLUE_TEAM_DOMAIN_QUEUES.json') as f:
    data = json.load(f)

sec = data['queues']['security']
print(f'Total security units: {len(sec)}')
print(f'P0: {sum(1 for u in sec if u["priority"]=="P0")}')
print(f'P1: {sum(1 for u in sec if u["priority"]=="P1")}')
print(f'P2: {sum(1 for u in sec if u["priority"]=="P2")}')
print(f'P3: {sum(1 for u in sec if u["priority"]=="P3")}')

# List all unit IDs for reference
print('\nAll security unit IDs:')
for u in sec:
    print(f'  {u["priority"]} - {u["unit_id"]}')

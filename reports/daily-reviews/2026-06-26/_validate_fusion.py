import json, sys
from collections import Counter

with open('/mnt/tool/2-projects/a-share-info-hub/reports/daily-reviews/2026-06-26/external-background-fusion.json', 'r') as f:
    data = json.load(f)

print('valid JSON')
print(f'schema_version: {data["schema_version"]}')
print(f'source_skill: {data["source_skill"]}')
print(f'trade_date: {data["trade_date"]}')
print(f'not_investment_advice: {data["not_investment_advice"]}')
print(f'topic_findings count: {len(data["topic_findings"])}')
print(f'risk_candidates count: {len(data["risk_candidates"])}')
print(f'follow_up_candidates count: {len(data["follow_up_candidates"])}')
print(f'citations count: {len(data["citations"])}')
print(f'information_gaps count: {len(data["information_gaps"])}')
print(f'issues count: {len(data["issues"])}')

topics = Counter(f['topic_key'] for f in data['topic_findings'])
print(f'\ntopic distribution:')
for k, v in sorted(topics.items()):
    print(f'  {k}: {v} findings')

types = Counter(f['type'] for f in data['topic_findings'])
print(f'\ntype distribution:')
for k, v in sorted(types.items()):
    print(f'  {k}: {v}')

for i, f in enumerate(data['topic_findings']):
    assert f['text'], f'finding {i} missing text'
    assert f['type'] in ('macro_fact', 'market_expectation', 'bank_view', 'inference'), f'finding {i} bad type'
    assert f['local_relevance'], f'finding {i} missing local_relevance'
    assert len(f['citations']) >= 1, f'finding {i} missing citations'
    for j, c in enumerate(f['citations']):
        assert c.get('source_name'), f'finding {i} citation {j} missing source_name'
        assert c.get('url', '').startswith('https://'), f'finding {i} citation {j} bad url'

print('\nall findings have required fields and valid citations')

forbidden = ['买入', '卖出', '建议买入', '建议卖出', '仓位建议', '目标价', '止盈', '止损', '明日必涨', '确定性主线']
text_all = json.dumps(data, ensure_ascii=False)
for fw in forbidden:
    if fw in text_all:
        print(f'WARNING: forbidden text found: {fw}')
        sys.exit(1)

print('no forbidden trading advice text detected')
print('\nall checks passed')

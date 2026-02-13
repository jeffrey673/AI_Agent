import requests, json, time

BASE = 'http://localhost:8100'
TOKEN = 'sk-skin1004'

TESTS = [
    ('skin1004-Analysis', '2024년 매출 알려줘'),
    ('skin1004-Analysis', '태국 쇼피 2024년 1월 매출'),
    ('skin1004-Analysis', '인도네시아 라자다 매출 Top 5 SKU'),
    ('skin1004-Analysis', '2024년 국가별 매출 비교'),
    ('skin1004-Analysis', '틱톡샵 매출 추이'),
    ('skin1004-Analysis', '아마존 미국 2024년 매출 요약'),
    ('skin1004-Analysis', '2024년 1분기 vs 2분기 매출 비교'),
    ('skin1004-Analysis', '필리핀 쇼피 베스트셀러 제품'),
    ('skin1004-Analysis', '안녕하세요'),
    ('skin1004-Analysis', 'SKIN1004가 뭐하는 회사야?'),
    ('skin1004-Analysis', '마다가스카르 센텔라란 뭐야?'),
    ('skin1004-Search', '스킨케어 트렌드 2024'),
    ('skin1004-Search', 'K-뷰티 시장 동향'),
    ('skin1004-Search', '센텔라 아시아티카 효능'),
    ('skin1004-Analysis', '말레이시아 매출 현황'),
    ('skin1004-Analysis', '2024년 12월 전체 매출'),
    ('skin1004-Analysis', '베트남 쇼피 매출 순위'),
    ('skin1004-Analysis', '제품별 매출 비중 차트'),
    ('skin1004-Analysis', '월별 매출 추이 그래프'),
    ('skin1004-Analysis', '2024년 하반기 매출 총합'),
    ('skin1004-Analysis', '가장 많이 팔린 제품 Top 10'),
    ('skin1004-Analysis', '국가별 플랫폼별 매출 크로스탭'),
    ('skin1004-Search', '인도네시아 화장품 시장 규모'),
    ('skin1004-Analysis', '2024년 성장률 분석'),
    ('skin1004-Analysis', '쇼피 vs 라자다 매출 비교'),
]

results = []
for i, (model, query) in enumerate(TESTS):
    try:
        start = time.time()
        r = requests.post(
            f'{BASE}/v1/chat/completions',
            headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': query}],
                'stream': False
            },
            timeout=120
        )
        elapsed = time.time() - start
        status = r.status_code

        if status == 200:
            data = r.json()
            answer = data.get('choices', [{}])[0].get('message', {}).get('content', '')[:80]
            result = 'OK'
        else:
            answer = r.text[:120]
            result = f'ERR-{status}'

        results.append((i+1, model, query[:25], status, f'{elapsed:.1f}s', result, answer if status != 200 else ''))
        marker = 'OK' if result == 'OK' else 'FAIL'
        print(f'[{i+1:2d}/25] {marker:4s} {status} {elapsed:6.1f}s  {model:20s}  {query[:30]}')
        if status != 200:
            print(f'        -> {answer}')
    except Exception as e:
        results.append((i+1, model, query[:25], 0, '?', f'EXCEPTION', str(e)[:80]))
        print(f'[{i+1:2d}/25] FAIL   0    ?.?s  {model:20s}  {query[:30]}')
        print(f'        -> {str(e)[:80]}')

print()
print('=' * 70)
ok = sum(1 for r in results if r[5] == 'OK')
err = sum(1 for r in results if r[5] != 'OK')
e404 = sum(1 for r in results if r[3] == 404)
print(f'Total: {len(results)} | OK: {ok} | Errors: {err} | 404: {e404}')
if err > 0:
    print()
    print('FAILURES:')
    for r in results:
        if r[5] != 'OK':
            print(f'  #{r[0]:2d} [{r[3]}] {r[2]:25s} -> {r[6]}')

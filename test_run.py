"""카카오 제외 전체 흐름 테스트"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
ROOT = os.path.dirname(os.path.abspath(__file__))

import yaml
from dotenv import load_dotenv
from notion_client import Client

from molit_api import fetch_transactions
from analyzer import analyze
import notion_updater as nc
import map_generator
load_dotenv(os.path.join(ROOT, '.env'))

with open(os.path.join(ROOT, 'config.yaml'), encoding='utf-8') as f:
    config = yaml.safe_load(f)

building = config['building']
search   = config['search']
molit_key    = os.environ['MOLIT_API_KEY']
notion_token = os.environ['NOTION_TOKEN']
page_id      = os.environ['NOTION_PARENT_PAGE_ID']

print('=' * 50)
print('1단계: MOLIT API 실거래가 수집')
print('=' * 50)

# 상업업무용 (mixed) 실거래가
transactions = fetch_transactions(
    lawd_cd=building['lawd_cd'],
    building_type=building['building_type'],
    area_m2=building.get('land_area_m2', 330.58),
    area_tolerance_pct=search['area_tolerance_pct'],
    months_back=search['months_back'],
    service_key=molit_key,
)
print(f'  수집 건수: {len(transactions)}건')
for t in transactions[:3]:
    print(f'  {t["date"]} | {t["building_name"] or "미상"} | {t["pyeong"]:.1f}평 | {t["price_man"]:,}만원')

if not transactions:
    print('  [주의] 데이터 없음 — lawd_cd/building_type 확인 필요')

print()
print('=' * 50)
print('2단계: 분석')
print('=' * 50)

result = analyze(transactions, [], building)
print(f'  추정 시세: {result["estimated_price_man"]:,}만원' if result['estimated_price_man'] else '  추정 시세: 데이터 부족')
yi = result.get('yield_info')
if yi:
    print(f'  총 수익률: {yi["gross_yield_pct"]}%')
    print(f'  갭 수익률: {yi["gap_yield_pct"]}%')
    print(f'  자기자본 수익률: {yi["equity_yield_pct"]}%')
    print(f'  매도 후 실수령(추정): {yi["net_proceeds_man"]:,}만원')

print()
print('=' * 50)
print('3단계: Notion DB 생성 및 데이터 기록')
print('=' * 50)

notion = Client(auth=notion_token)
db_ids = nc.setup_databases(notion, page_id)
print(f'  시세추이 DB: {db_ids["price_trend"]}')
print(f'  추천매물 DB: {db_ids["listings"]}')
print(f'  실거래가 DB: {db_ids["transactions"]}')

nc.update_price_trend(notion, db_ids['price_trend'], result)
print('  [OK] 시세 추이 기록')

nc.update_transactions(notion, db_ids['transactions'], transactions)
print(f'  [OK] 실거래가 {min(len(transactions), 20)}건 기록')

nc.update_summary_block(notion, page_id, result['summary'])
print('  [OK] 요약 블록 추가')

print()
print('=' * 50)
print('4단계: 네이버 지도 HTML 생성')
print('=' * 50)

naver_client_id = os.environ.get('NAVER_MAP_CLIENT_ID', '')

map_path = map_generator.generate(
    transactions=transactions,
    building=building,
    result=result,
    naver_client_id=naver_client_id,
)
print(f'  [OK] 지도 파일: {map_path}')

print()
print('=' * 50)
print('완료!')
print('  Notion: https://notion.so/' + page_id.replace('-', ''))
print(f'  지도:   {map_path}  (브라우저로 열거나 GitHub Pages로 배포)')
print('=' * 50)

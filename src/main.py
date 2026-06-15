"""메인 실행 진입점"""
import os
import sys
import yaml
from dotenv import load_dotenv
from notion_client import Client

from molit_api import fetch_transactions, fetch_candidates
from naver_crawler import fetch_listings
from analyzer import analyze
import notion_updater as nc
import kakao_client as kc
import map_generator


def _root():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def load_config() -> dict:
    with open(os.path.join(_root(), 'config.yaml'), encoding='utf-8') as f:
        return yaml.safe_load(f)


def main() -> None:
    load_dotenv(os.path.join(_root(), '.env'))

    config = load_config()
    building = config['building']
    search = config['search']
    naver = config['naver']
    cand_cfg = config.get('candidates', {})

    molit_key    = os.environ['MOLIT_API_KEY']
    notion_token = os.environ['NOTION_TOKEN']
    notion_page_id = os.environ['NOTION_PARENT_PAGE_ID']
    kakao_app_key  = os.environ.get('KAKAO_APP_KEY', '')
    kakao_refresh  = os.environ.get('KAKAO_REFRESH_TOKEN', '')
    naver_map_id   = os.environ.get('NAVER_MAP_CLIENT_ID', '')

    compare_area = building.get('land_area_m2') or building.get('area_m2', 84.0)

    print('🔍 실거래가 수집 중...')
    transactions = fetch_transactions(
        lawd_cd=building['lawd_cd'],
        building_type=building['building_type'],
        area_m2=compare_area,
        area_tolerance_pct=search['area_tolerance_pct'],
        months_back=search['months_back'],
        service_key=molit_key,
    )
    print(f'   → {len(transactions)}건 수집')

    print('🏗️  상가+주거 후보 건물 탐색 중...')
    candidates = []
    if cand_cfg.get('lawd_codes'):
        candidates = fetch_candidates(
            lawd_codes=cand_cfg['lawd_codes'],
            service_key=molit_key,
            months_back=cand_cfg.get('months_back', 12),
            min_area_m2=cand_cfg.get('min_land_area_m2', 250),
            use_keywords=cand_cfg.get('building_use_keywords', ['근린생활']),
        )
    print(f'   → {len(candidates)}건 후보')

    print('🔍 네이버 매물 수집 중...')
    listings = []
    try:
        listings = fetch_listings(
            cortar_no=naver['cortar_no'],
            real_estate_type=naver['real_estate_type'],
            area_m2=compare_area,
            area_tolerance_pct=search['area_tolerance_pct'],
        )
    except Exception as e:
        print(f'   → 네이버 수집 실패 (무시): {e}')
    print(f'   → {len(listings)}건 수집')

    print('📊 분석 중...')
    result = analyze(transactions, listings, building)

    print('📝 Notion 업데이트 중...')
    notion = Client(auth=notion_token)
    db_ids = nc.setup_databases(notion, notion_page_id)
    nc.update_price_trend(notion, db_ids['price_trend'], result)
    nc.update_transactions(notion, db_ids['transactions'], transactions)
    if candidates:
        market_avg = result.get('tx_stats', {}).get('avg_price_per_pyeong', 0)
        nc.update_candidates(notion, db_ids['listings'], candidates, market_avg)
    elif result['recommended']:
        nc.update_listings(notion, db_ids['listings'], result['recommended'])
    nc.update_summary_block(notion, notion_page_id, result['summary'])

    print('🗺️  지도 HTML 생성 중...')
    map_path = map_generator.generate(
        transactions=transactions,
        building=building,
        result=result,
        candidates=candidates,
        naver_client_id=naver_map_id,
    )
    print(f'   → {map_path}')

    if kakao_app_key and kakao_refresh:
        print('📱 카카오 알림 전송 중...')
        notion_url = f'https://notion.so/{notion_page_id.replace("-", "")}'
        new_refresh = kc.send_message(kakao_app_key, kakao_refresh, result['summary'], notion_url)
        if new_refresh:
            os.environ['KAKAO_REFRESH_TOKEN'] = new_refresh

    print('✅ 완료!')
    print(result['summary'])


if __name__ == '__main__':
    main()

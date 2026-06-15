"""Notion 대시보드 업데이트"""
from datetime import datetime
from notion_client import Client


DB_TITLES = {
    'price_trend': '📈 시세 추이',
    'listings': '🏘️ 추천 매물',
    'transactions': '📋 실거래가',
}


def _find_or_create_db(notion: Client, parent_page_id: str, title: str, properties: dict) -> str:
    results = notion.search(query=title, filter={'value': 'database', 'property': 'object'})
    for db in results.get('results', []):
        if db.get('title', [{}])[0].get('plain_text', '') == title:
            return db['id']

    db = notion.databases.create(
        parent={'type': 'page_id', 'page_id': parent_page_id},
        title=[{'type': 'text', 'text': {'content': title}}],
        properties=properties,
    )
    return db['id']


def setup_databases(notion: Client, parent_page_id: str) -> dict[str, str]:
    price_id = _find_or_create_db(notion, parent_page_id, DB_TITLES['price_trend'], {
        '주간리포트':      {'title': {}},
        '날짜':            {'date': {}},
        '추정가(만원)':    {'number': {'format': 'number_with_commas'}},
        '평균가(만원)':    {'number': {'format': 'number_with_commas'}},
        '최저가(만원)':    {'number': {'format': 'number_with_commas'}},
        '최고가(만원)':    {'number': {'format': 'number_with_commas'}},
        '거래건수':        {'number': {}},
        '평당가(만원)':    {'number': {'format': 'number_with_commas'}},
        '총수익률(%)':     {'number': {'format': 'number'}},
        '실질수익률(%)':   {'number': {'format': 'number'}},
    })

    listings_id = _find_or_create_db(notion, parent_page_id, DB_TITLES['listings'], {
        '매물명':          {'title': {}},
        '주소':            {'rich_text': {}},
        '면적(평)':        {'number': {'format': 'number'}},
        '호가(만원)':      {'number': {'format': 'number_with_commas'}},
        '평당가(만원)':    {'number': {'format': 'number_with_commas'}},
        '층수':            {'rich_text': {}},
        '특징':            {'rich_text': {}},
        '시장대비(%)':     {'number': {'format': 'number'}},
        '추정수익률(%)':   {'number': {'format': 'number'}},
        '네이버링크':      {'url': {}},
        '수집일':          {'date': {}},
        '상태':            {'select': {'options': [
            {'name': '신규', 'color': 'green'},
            {'name': '주시중', 'color': 'yellow'},
            {'name': '제외', 'color': 'gray'},
        ]}},
    })

    tx_id = _find_or_create_db(notion, parent_page_id, DB_TITLES['transactions'], {
        '건물명':          {'title': {}},
        '거래일':          {'date': {}},
        '대지면적(평)':    {'number': {'format': 'number'}},
        '거래금액(만원)':  {'number': {'format': 'number_with_commas'}},
        '평당가(만원)':    {'number': {'format': 'number_with_commas'}},
        '연면적(㎡)':      {'number': {'format': 'number'}},
        '건축년도':        {'rich_text': {}},
        '주소':            {'rich_text': {}},
    })

    return {'price_trend': price_id, 'listings': listings_id, 'transactions': tx_id}


def update_price_trend(notion: Client, db_id: str, result: dict) -> None:
    stats = result['tx_stats']
    today = result['report_date']
    yi = result.get('yield_info') or {}
    notion.pages.create(
        parent={'database_id': db_id},
        properties={
            '주간리포트':    {'title': [{'text': {'content': f'{today} 리포트'}}]},
            '날짜':          {'date': {'start': today}},
            '추정가(만원)':  {'number': result['estimated_price_man']},
            '평균가(만원)':  {'number': stats['avg_price_man']},
            '최저가(만원)':  {'number': stats['min_price_man']},
            '최고가(만원)':  {'number': stats['max_price_man']},
            '거래건수':      {'number': stats['count']},
            '평당가(만원)':  {'number': stats['avg_price_per_pyeong']},
            '총수익률(%)':   {'number': yi.get('gross_yield_pct', 0)},
            '실질수익률(%)': {'number': yi.get('net_yield_pct', 0)},
        },
    )


def update_candidates(notion: Client, db_id: str, candidates: list[dict],
                      market_avg_ppyeong: int) -> None:
    """상가+주거 후보 건물(MOLIT 실거래 기반)을 추천 매물 DB에 기록"""
    today = datetime.now().strftime('%Y-%m-%d')
    for c in candidates[:10]:
        ppyeong = c['price_per_pyeong']
        discount = round((market_avg_ppyeong - ppyeong) / market_avg_ppyeong * 100, 1) if market_avg_ppyeong > 0 else 0
        name = c.get('building_name') or f"{c['address']} {c.get('build_year', '')}년"
        feature = f"{c.get('build_year', '?')}년 준공 · {c['pyeong']:.0f}평 · 실거래가 기준"
        naver_link = (
            f"https://land.naver.com/search/search.naver"
            f"?searchKeyword={c['address'].replace(' ', '+')}"
        )
        notion.pages.create(
            parent={'database_id': db_id},
            properties={
                '매물명':        {'title': [{'text': {'content': f"[후보] {name}"}}]},
                '주소':          {'rich_text': [{'text': {'content': c['address']}}]},
                '면적(평)':      {'number': c['pyeong']},
                '호가(만원)':    {'number': c['price_man']},
                '평당가(만원)':  {'number': ppyeong},
                '층수':          {'rich_text': [{'text': {'content': c.get('floor', '-')}}]},
                '특징':          {'rich_text': [{'text': {'content': feature}}]},
                '시장대비(%)':   {'number': discount},
                '추정수익률(%)': {'number': 0},
                '네이버링크':    {'url': naver_link},
                '수집일':        {'date': {'start': c['date']}},
                '상태':          {'select': {'name': '신규'}},
            },
        )


def update_listings(notion: Client, db_id: str, recommended: list[dict]) -> None:
    today = datetime.now().strftime('%Y-%m-%d')
    for item in recommended:
        notion.pages.create(
            parent={'database_id': db_id},
            properties={
                '매물명':        {'title': [{'text': {'content': item['name']}}]},
                '주소':          {'rich_text': [{'text': {'content': item['address']}}]},
                '면적(평)':      {'number': item['pyeong']},
                '호가(만원)':    {'number': item['price_man']},
                '평당가(만원)':  {'number': item['price_per_pyeong']},
                '층수':          {'rich_text': [{'text': {'content': item['floor']}}]},
                '특징':          {'rich_text': [{'text': {'content': item.get('description', '')}}]},
                '시장대비(%)':   {'number': item.get('discount_pct', 0)},
                '추정수익률(%)': {'number': item.get('est_yield_pct') or 0},
                '네이버링크':    {'url': item['url']},
                '수집일':        {'date': {'start': today}},
                '상태':          {'select': {'name': '신규'}},
            },
        )


def update_transactions(notion: Client, db_id: str, transactions: list[dict]) -> None:
    for tx in transactions[:20]:
        notion.pages.create(
            parent={'database_id': db_id},
            properties={
                '건물명':         {'title': [{'text': {'content': tx['building_name'] or '미상'}}]},
                '거래일':         {'date': {'start': tx['date']}},
                '대지면적(평)':   {'number': tx['pyeong']},
                '거래금액(만원)': {'number': tx['price_man']},
                '평당가(만원)':   {'number': tx['price_per_pyeong']},
                '연면적(㎡)':     {'number': tx.get('total_floor_area_m2', 0)},
                '건축년도':       {'rich_text': [{'text': {'content': tx.get('build_year', '')}}]},
                '주소':           {'rich_text': [{'text': {'content': tx['address']}}]},
            },
        )


def update_summary_block(notion: Client, parent_page_id: str, summary: str) -> None:
    notion.blocks.children.append(
        block_id=parent_page_id,
        children=[{
            'object': 'block',
            'type': 'callout',
            'callout': {
                'rich_text': [{'type': 'text', 'text': {'content': summary}}],
                'icon': {'type': 'emoji', 'emoji': '🏢'},
                'color': 'blue_background',
            },
        }],
    )

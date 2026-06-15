"""국토교통부 실거래가 공공 API 클라이언트"""
import requests
import xmltodict
from datetime import datetime


BASE = 'https://apis.data.go.kr/1613000'
ENDPOINTS = {
    'apartment': f'{BASE}/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade',
    'villa':     f'{BASE}/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade',
    'officetel': f'{BASE}/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade',
    'detached':  f'{BASE}/RTMSDataSvcSHTrade/getRTMSDataSvcSHTrade',
    'mixed':     f'{BASE}/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade',
}

# 한국어 필드 타입 (아파트/빌라/오피스텔/단독)
KO_META = {
    'apartment': {'area_field': '전용면적', 'name_field': '아파트'},
    'villa':     {'area_field': '전용면적', 'name_field': '연립다세대'},
    'officetel': {'area_field': '전용면적', 'name_field': '단지명'},
    'detached':  {'area_field': '대지면적', 'name_field': '건물주용도'},
}


def _months_ago(n: int) -> tuple[int, int]:
    now = datetime.now()
    month = now.month - n
    year = now.year
    while month <= 0:
        month += 12
        year -= 1
    return year, month


def _parse_ko(item: dict, meta: dict) -> dict:
    """한국어 필드 응답 파싱 (아파트/빌라/오피스텔/단독)"""
    price = int(item.get('거래금액', '0').replace(',', '').strip()) * 10000
    area = float(str(item.get(meta['area_field'], '0')).strip())
    d_year = item.get('년', '')
    d_month = str(item.get('월', '')).zfill(2)
    d_day = str(item.get('일', '')).zfill(2)
    pyeong = area / 3.3058
    return {
        'date': f'{d_year}-{d_month}-{d_day}',
        'price_man': price // 10000,
        'area_m2': area,
        'pyeong': round(pyeong, 1),
        'price_per_pyeong': round(price / pyeong / 10000) if pyeong > 0 else 0,
        'building_name': str(item.get(meta['name_field'], '')).strip(),
        'floor': str(item.get('층', '-')).strip(),
        'address': item.get('도로명', item.get('지번', '')).strip(),
        'total_floor_area_m2': float(str(item.get('연면적', 0) or 0)),
        'build_year': str(item.get('건축년도', '')).strip(),
    }


def _parse_mixed(item: dict) -> dict:
    """영어 필드 응답 파싱 (상업업무용 — getRTMSDataSvcNrgTrade)"""
    price_man = int(str(item.get('dealAmount', '0')).replace(',', '').strip())
    # plottageAr = 대지면적(㎡), buildingAr = 건물면적(㎡)
    area = float(str(item.get('plottageAr') or 0))
    bldg_area = float(str(item.get('buildingAr') or 0))
    pyeong = area / 3.3058
    d = f"{item.get('dealYear','')}-{str(item.get('dealMonth','')).zfill(2)}-{str(item.get('dealDay','')).zfill(2)}"
    dong = str(item.get('umdNm', '')).strip()
    jibun = str(item.get('jibun', '')).strip()
    return {
        'date': d,
        'price_man': price_man,
        'area_m2': area,
        'pyeong': round(pyeong, 1),
        'price_per_pyeong': round(price_man / pyeong) if pyeong > 0 else 0,
        'building_name': str(item.get('buildingUse', '')).strip(),
        'floor': str(item.get('floor') or '-').strip(),
        'address': f'{dong} {jibun}'.strip(),
        'total_floor_area_m2': bldg_area,
        'build_year': str(item.get('buildYear', '')).strip(),
    }


def fetch_transactions(lawd_cd: str, building_type: str, area_m2: float,
                       area_tolerance_pct: int, months_back: int, service_key: str) -> list[dict]:
    endpoint = ENDPOINTS.get(building_type, ENDPOINTS['mixed'])
    is_mixed = (building_type == 'mixed')
    meta = KO_META.get(building_type)

    area_min = area_m2 * (1 - area_tolerance_pct / 100)
    area_max = area_m2 * (1 + area_tolerance_pct / 100)

    transactions = []
    for i in range(months_back):
        year, month = _months_ago(i)
        deal_ymd = f'{year}{month:02d}'
        try:
            resp = requests.get(endpoint, params={
                'LAWD_CD': lawd_cd,
                'DEAL_YMD': deal_ymd,
                'serviceKey': service_key,
                'numOfRows': 1000,
                'pageNo': 1,
            }, timeout=15)
            resp.raise_for_status()
            data = xmltodict.parse(resp.text)
            items = data.get('response', {}).get('body', {}).get('items') or {}
            item_list = items.get('item', [])
            if isinstance(item_list, dict):
                item_list = [item_list]

            for item in item_list:
                try:
                    parsed = _parse_mixed(item) if is_mixed else _parse_ko(item, meta)
                    area = parsed['area_m2']
                    # 상업업무용은 대지면적 없는 집합건물도 있어 area=0이면 건물면적으로 대체
                    if area == 0:
                        area = parsed['total_floor_area_m2']
                        parsed['area_m2'] = area
                        parsed['pyeong'] = round(area / 3.3058, 1)
                    if area > 0 and not (area_min <= area <= area_max):
                        continue
                    transactions.append(parsed)
                except (ValueError, TypeError):
                    continue
        except Exception as e:
            print(f'[국토부API] {deal_ymd} 수집 실패: {e}')

    return sorted(transactions, key=lambda x: x['date'], reverse=True)


def fetch_candidates(lawd_codes: list, service_key: str, months_back: int,
                     min_area_m2: float, use_keywords: list) -> list[dict]:
    """여러 지역에서 상가+주거 후보 건물 검색 (면적 하한 필터 + 건물용도 필터)"""
    endpoint = ENDPOINTS['mixed']
    results = []

    for lawd_cd in lawd_codes:
        for i in range(months_back):
            year, month = _months_ago(i)
            deal_ymd = f'{year}{month:02d}'
            try:
                resp = requests.get(endpoint, params={
                    'LAWD_CD': lawd_cd,
                    'DEAL_YMD': deal_ymd,
                    'serviceKey': service_key,
                    'numOfRows': 1000,
                    'pageNo': 1,
                }, timeout=15)
                resp.raise_for_status()
                data = xmltodict.parse(resp.text)
                items = data.get('response', {}).get('body', {}).get('items') or {}
                item_list = items.get('item', [])
                if isinstance(item_list, dict):
                    item_list = [item_list]

                for item in item_list:
                    try:
                        parsed = _parse_mixed(item)
                        area = parsed['area_m2'] or parsed['total_floor_area_m2']
                        parsed['area_m2'] = area
                        if area < min_area_m2:
                            continue
                        use = parsed.get('building_name', '')
                        if use_keywords and not any(kw in use for kw in use_keywords):
                            continue
                        parsed['lawd_cd'] = lawd_cd
                        results.append(parsed)
                    except (ValueError, TypeError):
                        continue
            except Exception as e:
                print(f'[후보건물] {lawd_cd} {deal_ymd} 실패: {e}')

    # 중복 제거 후 최신순 정렬
    seen: set = set()
    unique = []
    for r in sorted(results, key=lambda x: x['date'], reverse=True):
        key = f"{r['address']}{r['date']}{r['price_man']}"
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:15]

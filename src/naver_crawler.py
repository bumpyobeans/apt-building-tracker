"""네이버 부동산 현재 매물(호가) 크롤러"""
import requests
import re


_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36',
    'Referer': 'https://new.land.naver.com/',
    'Accept': 'application/json, text/plain, */*',
}


def _get_auth_token() -> str | None:
    try:
        resp = requests.get('https://new.land.naver.com/', headers=_HEADERS, timeout=10)
        match = re.search(r'eyJhbGci[A-Za-z0-9._-]+', resp.text)
        return match.group(0) if match else None
    except Exception:
        return None


def fetch_listings(cortar_no: str, real_estate_type: str,
                   area_m2: float, area_tolerance_pct: int) -> list[dict]:
    token = _get_auth_token()
    headers = dict(_HEADERS)
    if token:
        headers['Authorization'] = f'Bearer {token}'

    area_min = int(area_m2 * (1 - area_tolerance_pct / 100))
    area_max = int(area_m2 * (1 + area_tolerance_pct / 100))

    listings = []
    try:
        resp = requests.get(
            'https://new.land.naver.com/api/articles',
            params={
                'cortarNo': cortar_no,
                'order': 'rank',
                'realEstateType': real_estate_type,
                'tradeType': 'A1',
                'areaMin': area_min,
                'areaMax': area_max,
                'page': 1,
                'tag': f'::{real_estate_type}:false:false:false:false:false:false:A1::',
                'rentPriceMin': 0,
                'rentPriceMax': 900000000,
                'priceMin': 0,
                'priceMax': 900000000,
                'showArticle': 'false',
                'sameAddressGroup': 'false',
            },
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in data.get('articleList', []):
            price_raw = item.get('dealOrWarrantPrc', '0').replace(',', '').replace('억', '').strip()
            try:
                # 네이버는 "15억" 같은 형식 → 파싱
                price_str = item.get('dealOrWarrantPrc', '0')
                price_man = _parse_naver_price(price_str)
                area = float(item.get('area2', 0))
                listings.append({
                    'article_no': item.get('articleNo', ''),
                    'name': item.get('articleName', ''),
                    'address': item.get('buildingName', ''),
                    'floor': item.get('floorInfo', ''),
                    'area_m2': area,
                    'pyeong': round(area / 3.3058, 1),
                    'price_man': price_man,
                    'price_per_pyeong': round(price_man / (area / 3.3058)) if area > 0 else 0,
                    'description': item.get('articleFeatureDesc', ''),
                    'url': f"https://new.land.naver.com/매물?articleNo={item.get('articleNo', '')}",
                })
            except (ValueError, TypeError):
                continue
    except Exception as e:
        print(f'[네이버] 매물 수집 실패: {e}')

    return sorted(listings, key=lambda x: x['price_man'])


def _parse_naver_price(price_str: str) -> int:
    """'15억 5,000' → 155000 (만원)"""

    price_str = price_str.replace(',', '').strip()
    if '억' in price_str:
        parts = price_str.split('억')
        eok = int(parts[0].strip()) * 10000
        man = int(parts[1].strip()) if parts[1].strip() else 0
        return eok + man
    return int(price_str) if price_str.isdigit() else 0

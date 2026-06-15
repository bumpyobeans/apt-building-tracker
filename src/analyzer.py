"""실거래가 + 매물 데이터 분석 및 추천 생성"""
from datetime import datetime


def analyze(transactions: list[dict], listings: list[dict], building: dict) -> dict:
    my_name = building['name']
    land_m2 = building.get('land_area_m2') or building.get('area_m2', 0)
    my_pyeong = land_m2 / 3.3058

    tx_stats = _transaction_stats(transactions)

    estimated_price_man = 0
    if tx_stats['avg_price_per_pyeong'] > 0:
        estimated_price_man = round(tx_stats['avg_price_per_pyeong'] * my_pyeong)

    yield_info = _calc_yield(building, estimated_price_man)
    recommended = _pick_recommendations(listings, tx_stats['avg_price_per_pyeong'], building)
    summary = _build_summary(tx_stats, estimated_price_man, my_name, my_pyeong, recommended, yield_info, building)

    return {
        'tx_stats': tx_stats,
        'estimated_price_man': estimated_price_man,
        'yield_info': yield_info,
        'recommended': recommended,
        'summary': summary,
        'report_date': datetime.now().strftime('%Y-%m-%d'),
    }


def _transaction_stats(transactions: list[dict]) -> dict:
    if not transactions:
        return {'count': 0, 'avg_price_man': 0, 'min_price_man': 0,
                'max_price_man': 0, 'avg_price_per_pyeong': 0,
                'median_price_man': 0, 'recent_3_avg': 0}
    prices = [t['price_man'] for t in transactions]
    ppyeongs = [t['price_per_pyeong'] for t in transactions if t['price_per_pyeong'] > 0]
    sorted_prices = sorted(prices)
    n = len(sorted_prices)
    median = sorted_prices[n // 2] if n % 2 else (sorted_prices[n//2 - 1] + sorted_prices[n//2]) // 2
    # 최근 3건 평균 (날짜 기준 이미 정렬됨)
    recent3 = round(sum(prices[:3]) / min(3, len(prices)))
    return {
        'count': len(transactions),
        'avg_price_man': round(sum(prices) / len(prices)),
        'min_price_man': min(prices),
        'max_price_man': max(prices),
        'median_price_man': median,
        'recent_3_avg': recent3,
        'avg_price_per_pyeong': round(sum(ppyeongs) / len(ppyeongs)) if ppyeongs else 0,
    }


def _calc_yield(building: dict, estimated_price_man: int) -> dict | None:
    monthly_rent = building.get('monthly_rent_man', 0)
    shop_deposit = building.get('shop_deposit_man', 0)
    jeonse_deposit = building.get('jeonse_deposit_man', 0)
    loan = building.get('loan_man', 0)

    if not monthly_rent or not estimated_price_man:
        return None

    annual_rent_man = monthly_rent * 12
    total_deposit_man = shop_deposit + jeonse_deposit

    # 갭 투자금: 매매가 - 임차인 보증금 합계
    gap_man = estimated_price_man - total_deposit_man
    # 자기자본: 갭 투자금에서 대출까지 차감한 실제 내 돈
    equity_man = gap_man - loan

    gross_yield_pct = round(annual_rent_man / estimated_price_man * 100, 2)
    gap_yield_pct = round(annual_rent_man / gap_man * 100, 2) if gap_man > 0 else None
    equity_yield_pct = round(annual_rent_man / equity_man * 100, 2) if equity_man > 0 else None

    # 매도 시 실수령액: 매매가 - 보증금 반환 - 대출 상환
    net_proceeds_man = estimated_price_man - total_deposit_man - loan

    # 목표 수익률별 적정 매매가 역산
    target_prices = {
        '4%':   round(annual_rent_man / 0.04),
        '4.5%': round(annual_rent_man / 0.045),
        '5%':   round(annual_rent_man / 0.05),
    }

    return {
        'monthly_rent_man': monthly_rent,
        'annual_rent_man': annual_rent_man,
        'shop_deposit_man': shop_deposit,
        'jeonse_deposit_man': jeonse_deposit,
        'total_deposit_man': total_deposit_man,
        'loan_man': loan,
        'gap_man': gap_man,
        'equity_man': equity_man,
        'net_proceeds_man': net_proceeds_man,
        'gross_yield_pct': gross_yield_pct,
        'gap_yield_pct': gap_yield_pct,
        'equity_yield_pct': equity_yield_pct,
        'target_prices': target_prices,
    }


def _pick_recommendations(listings: list[dict], market_avg_ppyeong: int, building: dict) -> list[dict]:
    if not listings:
        return []

    monthly_rent = building.get('monthly_rent_man', 0)
    scored = []
    for listing in listings:
        ppyeong = listing['price_per_pyeong']
        if ppyeong <= 0:
            continue
        discount_pct = round((market_avg_ppyeong - ppyeong) / market_avg_ppyeong * 100, 1) if market_avg_ppyeong > 0 else 0
        est_yield_pct = round(monthly_rent * 12 / listing['price_man'] * 100, 2) if monthly_rent and listing['price_man'] > 0 else None
        scored.append({**listing, 'discount_pct': discount_pct, 'est_yield_pct': est_yield_pct})

    scored.sort(key=lambda x: x['price_per_pyeong'])
    return scored[:5]


def _build_summary(tx_stats: dict, estimated_price_man: int, my_name: str,
                   my_pyeong: float, recommended: list[dict], yield_info: dict | None,
                   building: dict | None = None) -> str:
    lines = []
    lines.append(f'📅 {datetime.now().strftime("%Y년 %m월 %d일")} 주간 부동산 시세 리포트')
    lines.append('')
    b           = building or {}
    floors      = b.get('total_floors', '-')
    shop_u      = b.get('shop_units', '-')
    shop_fl     = b.get('shop_floors', '1층')
    resi_u      = b.get('residential_units', '-')
    resi_fl     = b.get('residential_floors', '2층')
    owner_fl    = b.get('owner_floor', '-')
    lines.append(f'🏢 {my_name}')
    lines.append(f'   대지: {my_pyeong:.1f}평  |  지상 {floors}층  |  상가+주거')
    lines.append(f'   근린생활시설: {shop_u}개 ({shop_fl})  |  주거: {resi_u}세대 ({resi_fl})  |  주인거주: {owner_fl}층')

    if estimated_price_man > 0:
        lines.append(f'   추정 시세: {_fmt(estimated_price_man)}')
    else:
        lines.append('   추정 시세: 데이터 부족')

    if yield_info:
        yi = yield_info
        lines.append(f'   월세 수입: {yi["monthly_rent_man"]:,}만원/월 (연 {_fmt(yi["annual_rent_man"])})')
        lines.append(f'   보증금: 전세 {_fmt(yi["jeonse_deposit_man"])} + 상가 {_fmt(yi["shop_deposit_man"])} = {_fmt(yi["total_deposit_man"])}')
        lines.append(f'   대출: {_fmt(yi["loan_man"])}  |  자기자본: {_fmt(yi["equity_man"])}')
        yield_str = f'총 {yi["gross_yield_pct"]}%'
        if yi['gap_yield_pct']:
            yield_str += f'  |  갭 {yi["gap_yield_pct"]}%'
        if yi['equity_yield_pct']:
            yield_str += f'  |  자기자본 {yi["equity_yield_pct"]}%'
        lines.append(f'   수익률: {yield_str}')
        tp = yi['target_prices']
        lines.append(f'   적정 매매가: 4%={_fmt(tp["4%"])} / 4.5%={_fmt(tp["4.5%"])} / 5%={_fmt(tp["5%"])}')
        lines.append(f'   매도 후 실수령 (추정): {_fmt(yi["net_proceeds_man"])} (보증금 반환+대출상환 후)')

    lines.append('')
    lines.append(f'📊 현재 시세 (최근 6개월 실거래 {tx_stats["count"]}건)')
    if tx_stats['count'] > 0:
        lines.append(f'   평당 시세:   {tx_stats["avg_price_per_pyeong"]:,}만원/평')
        lines.append(f'   최근 3건 평균: {_fmt(tx_stats["recent_3_avg"])}')
        lines.append(f'   중간값:      {_fmt(tx_stats["median_price_man"])}')
        lines.append(f'   거래 범위:   {_fmt(tx_stats["min_price_man"])} ~ {_fmt(tx_stats["max_price_man"])}')

    if recommended:
        lines.append('')
        lines.append(f'🌟 추천 매물 ({len(recommended)}건)')
        for i, r in enumerate(recommended[:3], 1):
            discount = f' (시장대비 {r["discount_pct"]:+.1f}%)' if r['discount_pct'] != 0 else ''
            yield_str = f' | 수익률 {r["est_yield_pct"]}%' if r.get('est_yield_pct') else ''
            lines.append(f'   {i}. {r["name"]} | {r["pyeong"]:.1f}평 | {_fmt(r["price_man"])}{discount}{yield_str}')

    lines.append('')
    lines.append('👉 Notion에서 전체 내용 확인하세요.')
    return '\n'.join(lines)


def _fmt(price_man: int) -> str:
    if price_man >= 10000:
        eok = price_man // 10000
        rem = price_man % 10000
        return f'{eok}억 {rem:,}만원' if rem else f'{eok}억'
    return f'{price_man:,}만원'

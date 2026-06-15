"""거래 데이터 → 네이버 지도 HTML 생성기

지오코딩은 브라우저 내 Naver Maps JS API로 처리.
Python 쪽에서는 REST Geocoding API 호출 없음.
"""
import json
import math
import os

DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs')

# 남양주시 읍/동별 중심 좌표 — JS 지오코딩 전 초기 위치용
DONG_COORDS = {
    '별내동':  (37.6252, 127.1386),
    '다산동':  (37.6355, 127.1980),
    '진접읍':  (37.7014, 127.1988),
    '화도읍':  (37.6383, 127.3011),
    '퇴계원읍': (37.6522, 127.1502),
    '오남읍':  (37.6761, 127.2202),
    '와부읍':  (37.6005, 127.1674),
    '호평동':  (37.6517, 127.1869),
    '평내동':  (37.6517, 127.1900),
    '금곡동':  (37.6161, 127.1669),
    '양정동':  (37.6277, 127.1786),
    '수동면':  (37.7394, 127.2919),
    '조안면':  (37.5969, 127.3072),
}
NAMYANGJU_CENTER = (37.6363, 127.2163)


def _spread(lat: float, lng: float, idx: int) -> tuple[float, float]:
    """같은 위치 마커가 겹치지 않도록 황금각도로 분산"""
    if idx == 0:
        return lat, lng
    angle = idx * 137.508 * math.pi / 180
    r = 0.0004 * math.sqrt(idx)
    return lat + r * math.cos(angle), lng + r * math.sin(angle)


def _fmt(price_man: int) -> str:
    if price_man >= 10000:
        eok = price_man // 10000
        rem = price_man % 10000
        return f'{eok}억 {rem:,}만원' if rem else f'{eok}억'
    return f'{price_man:,}만원'


def generate(transactions: list[dict], building: dict, result: dict,
             candidates: list[dict] | None = None,
             naver_client_id: str = '', **_) -> str:
    """거래 데이터를 받아 docs/index.html 생성. 파일 경로 반환."""
    os.makedirs(DOCS_DIR, exist_ok=True)

    # ── 거래 마커 데이터 ────────────────────────────────────────────────────
    coord_count: dict[str, int] = {}
    markers = []

    for tx in transactions:
        parts = tx.get('address', '').split()
        dong = parts[0] if parts else ''
        coords = DONG_COORDS.get(dong, NAMYANGJU_CENTER)

        key = f'{coords[0]:.4f},{coords[1]:.4f}'
        n = coord_count.get(key, 0)
        coord_count[key] = n + 1
        lat, lng = _spread(coords[0], coords[1], n)

        markers.append({
            'lat': round(lat, 6),
            'lng': round(lng, 6),
            'date': tx['date'],
            'price_man': tx['price_man'],
            'price_label': _fmt(tx['price_man']),
            'pyeong': tx['pyeong'],
            'price_per_pyeong': tx['price_per_pyeong'],
            'building_name': tx.get('building_name', ''),
            'address': tx.get('address', ''),
            'floor': tx.get('floor', '-'),
            'build_year': tx.get('build_year', ''),
        })

    # ── 내 건물 데이터 (JS에서 정밀 지오코딩) ──────────────────────────────
    fallback = DONG_COORDS.get('별내동', NAMYANGJU_CENTER)
    my_building = {
        'lat': fallback[0],
        'lng': fallback[1],
        'name': building.get('name', '내 건물'),
        'address': building.get('address', ''),
        'estimated_price': _fmt(result.get('estimated_price_man', 0)),
    }

    stats = result.get('tx_stats', {})
    summary = {
        'count': len(transactions),
        'estimated_price': _fmt(result.get('estimated_price_man', 0)),
        'avg_ppyeong': stats.get('avg_price_per_pyeong', 0),
        'report_date': result.get('report_date', ''),
    }

    yi = result.get('yield_info') or {}
    yield_info = {
        'gross': yi.get('gross_yield_pct', '-'),
        'gap': yi.get('gap_yield_pct', '-'),
        'equity': yi.get('equity_yield_pct', '-'),
        'net_proceeds': _fmt(yi['net_proceeds_man']) if yi.get('net_proceeds_man') else '-',
    }

    # ── 후보 건물 마커 ──────────────────────────────────────────────────────
    cand_markers = []
    cand_coord_count: dict[str, int] = {}
    for c in (candidates or []):
        parts = c.get('address', '').split()
        dong = parts[0] if parts else ''
        coords = DONG_COORDS.get(dong, NAMYANGJU_CENTER)
        key = f'{coords[0]:.4f},{coords[1]:.4f}'
        n = cand_coord_count.get(key, 0)
        cand_coord_count[key] = n + 1
        lat, lng = _spread(coords[0], coords[1], n + 30)  # offset과 구분
        cand_markers.append({
            'lat': round(lat, 6), 'lng': round(lng, 6),
            'date': c['date'], 'price_man': c['price_man'],
            'price_label': _fmt(c['price_man']),
            'pyeong': c['pyeong'],
            'price_per_pyeong': c['price_per_pyeong'],
            'building_name': c.get('building_name', ''),
            'address': c.get('address', ''),
            'floor': c.get('floor', '-'),
            'build_year': c.get('build_year', ''),
        })

    data_json = json.dumps(
        {'transactions': markers, 'my_building': my_building,
         'candidates': cand_markers, 'summary': summary, 'yield_info': yield_info},
        ensure_ascii=False,
    )

    client_id = naver_client_id or 'YOUR_NAVER_CLIENT_ID'
    html = _TEMPLATE.replace('{{CLIENT_ID}}', client_id) \
                    .replace('{{MAP_DATA}}', data_json)

    out = os.path.join(DOCS_DIR, 'index.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)

    return out


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>별내동 건물 시세 지도</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; }
body { font-family: -apple-system, 'Apple SD Gothic Neo', '맑은 고딕', sans-serif;
       background: #f4f6f9; color: #222; }
#layout { display: flex; height: 100vh; }
#sidebar { width: 340px; min-width: 280px; overflow-y: auto;
           background: #fff; box-shadow: 2px 0 8px rgba(0,0,0,.08); z-index: 10; flex-shrink: 0; }
#map { flex: 1; min-width: 0; }
.panel { padding: 16px; border-bottom: 1px solid #eee; }
.panel h2 { font-size: 15px; color: #333; margin-bottom: 8px; }
.summary-card { background: #f0f4ff; border-radius: 8px; padding: 12px; }
.summary-card .price { font-size: 22px; font-weight: 700; color: #1a73e8; }
.summary-card .meta { font-size: 12px; color: #666; margin-top: 4px; line-height: 1.5; }
.yield-row { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
.yield-chip { flex: 1; min-width: 56px; background: #fff; border: 1px solid #dde;
              border-radius: 6px; padding: 6px 4px; text-align: center; }
.yield-chip .label { font-size: 10px; color: #888; }
.yield-chip .val { font-size: 13px; font-weight: 700; color: #1a73e8; margin-top: 2px; }
#tx-list { list-style: none; }
#tx-list li { padding: 10px 16px; border-bottom: 1px solid #f0f0f0;
              cursor: pointer; transition: background .15s; }
#tx-list li:hover { background: #f5f8ff; }
.tx-date { font-size: 11px; color: #999; }
.tx-price { font-size: 14px; font-weight: 600; color: #e83a1a; margin: 2px 0; }
.tx-info { font-size: 12px; color: #555; }
.badge { display: inline-block; padding: 1px 6px; border-radius: 4px;
         font-size: 10px; font-weight: 600; margin-left: 4px; vertical-align: middle; }
.leaflet-popup-content { margin: 10px 14px; min-width: 180px; }
@media (max-width: 600px) {
  #layout { flex-direction: column; }
  #sidebar { width: 100%; height: 44vh; flex-shrink: 0; }
  #map { height: 56vh; }
}
</style>
</head>
<body>
<div id="layout">
  <div id="sidebar">
    <div class="panel">
      <h2>📍 별내동 건물 시세 지도</h2>
      <div class="summary-card" id="summary-card"></div>
    </div>
    <div class="panel">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:11px;color:#666;margin-bottom:8px">
        <span>🟠 내 건물</span>
        <span>🔵 실거래가</span>
        <span>🟢 후보 건물</span>
      </div>
      <h2>실거래가 목록 (<span id="tx-count">0</span>건)</h2>
      <ul id="tx-list"></ul>
    </div>
    <div class="panel">
      <h2>매수 후보 건물 (<span id="cand-count">0</span>건)</h2>
      <ul id="cand-list"></ul>
    </div>
  </div>
  <div id="map"></div>
</div>

<script>
var RAW = {{MAP_DATA}};
var mb = RAW.my_building;

// ── 요약 카드 ──────────────────────────────────────────────────────────────
(function() {
  var s = RAW.summary, y = RAW.yield_info;
  document.getElementById('summary-card').innerHTML =
    '<div class="price">' + s.estimated_price + '</div>' +
    '<div class="meta">추정 매매가 &nbsp;|&nbsp; ' + s.report_date + '<br>' +
      s.count + '건 평균 ' + s.avg_ppyeong.toLocaleString() + '만원/평</div>' +
    '<div class="yield-row">' +
      '<div class="yield-chip"><div class="label">총 수익률</div><div class="val">' + y.gross + '%</div></div>' +
      '<div class="yield-chip"><div class="label">갭 수익률</div><div class="val">' + y.gap + '%</div></div>' +
      '<div class="yield-chip"><div class="label">자기자본</div><div class="val">' + y.equity + '%</div></div>' +
      '<div class="yield-chip"><div class="label">실수령 예상</div><div class="val" style="font-size:11px">' + y.net_proceeds + '</div></div>' +
    '</div>';
})();

// ── 지도 초기화 (Leaflet + OpenStreetMap) ────────────────────────────────
var map = L.map('map').setView([mb.lat, mb.lng], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  maxZoom: 19,
}).addTo(map);

// ── 내 건물 마커 ──────────────────────────────────────────────────────────
var myIcon = L.divIcon({
  className: '',
  html: '<div style="background:#ff6b35;color:#fff;padding:5px 10px;border-radius:8px;' +
        'font-size:12px;font-weight:700;white-space:nowrap;' +
        'box-shadow:0 2px 8px rgba(0,0,0,.4);transform:translateX(-50%)">🏠 ' + mb.name + '</div>',
  iconSize: null, iconAnchor: [0, 0],
});
L.marker([mb.lat, mb.lng], { icon: myIcon, zIndexOffset: 1000 })
  .addTo(map)
  .bindPopup(
    '<b style="font-size:14px">' + mb.name + '</b><br>' +
    '<span style="color:#888;font-size:12px">' + mb.address + '</span><br>' +
    '<span style="color:#ff6b35;font-weight:700;font-size:16px">추정 시세: ' + mb.estimated_price + '</span>'
  );

// ── 거래 마커 + 목록 ──────────────────────────────────────────────────────
var list = document.getElementById('tx-list');
document.getElementById('tx-count').textContent = RAW.transactions.length;

// ── 후보 건물 마커 (녹색) ───────────────────────────────────────────────
var candList = document.getElementById('cand-list');
document.getElementById('cand-count').textContent = RAW.candidates.length;

RAW.candidates.forEach(function(c) {
  var icon = L.divIcon({
    className: '',
    html: '<div style="background:#27ae60;color:#fff;padding:3px 8px;border-radius:5px;' +
          'font-size:10px;font-weight:700;white-space:nowrap;' +
          'box-shadow:0 1px 4px rgba(0,0,0,.3);transform:translateX(-50%)">' + c.price_label + '</div>',
    iconSize: null, iconAnchor: [0, 0],
  });

  var popup =
    '<b style="color:#27ae60;font-size:14px">🟢 후보 ' + c.price_label + '</b><br>' +
    c.date + ' · ' + c.pyeong + '평 · ' + c.price_per_pyeong.toLocaleString() + '만원/평<br>' +
    (c.building_name ? '<span style="color:#444">' + c.building_name + '</span><br>' : '') +
    '<span style="color:#888;font-size:11px">' + c.address +
    (c.floor && c.floor !== '-' ? ' ' + c.floor + '층' : '') + '</span><br>' +
    '<span style="color:#aaa;font-size:11px">준공: ' + (c.build_year || '미상') + '</span><br>' +
    '<a href="https://land.naver.com/search/search.naver?searchKeyword=' +
    encodeURIComponent(c.address) + '" target="_blank" style="color:#27ae60;font-size:11px">네이버 부동산 검색 →</a>';

  var marker = L.marker([c.lat, c.lng], { icon: icon }).addTo(map).bindPopup(popup);

  var li = document.createElement('li');
  li.innerHTML =
    '<div class="tx-date">' + c.date + ' · 실거래가 기준</div>' +
    '<div class="tx-price" style="color:#27ae60">' + c.price_label +
      '<span class="badge" style="background:#27ae60;color:#fff">' + c.pyeong + '평</span>' +
      '<span class="badge" style="background:#eee;color:#555">' + c.price_per_pyeong.toLocaleString() + '만/평</span>' +
    '</div>' +
    '<div class="tx-info">' + c.address + (c.building_name ? ' · ' + c.building_name : '') + '</div>';
  li.style.cursor = 'pointer';
  li.addEventListener('click', function() {
    map.setView([c.lat, c.lng], 15);
    marker.openPopup();
  });
  candList.appendChild(li);
});

// ── 실거래가 마커 (파란색) ───────────────────────────────────────────────
RAW.transactions.forEach(function(m) {
  var icon = L.divIcon({
    className: '',
    html: '<div style="background:#1a73e8;color:#fff;padding:3px 8px;border-radius:5px;' +
          'font-size:10px;font-weight:700;white-space:nowrap;' +
          'box-shadow:0 1px 4px rgba(0,0,0,.3);transform:translateX(-50%)">' + m.price_label + '</div>',
    iconSize: null, iconAnchor: [0, 0],
  });

  var popup =
    '<b style="color:#1a73e8;font-size:15px">' + m.price_label + '</b><br>' +
    m.date + ' · ' + m.pyeong + '평 · ' + m.price_per_pyeong.toLocaleString() + '만원/평<br>' +
    (m.building_name ? '<span style="color:#444">' + m.building_name + '</span><br>' : '') +
    '<span style="color:#888;font-size:11px">' + m.address +
    (m.floor && m.floor !== '-' ? ' ' + m.floor + '층' : '') + '</span><br>' +
    '<span style="color:#aaa;font-size:11px">준공: ' + (m.build_year || '미상') + '</span>';

  var marker = L.marker([m.lat, m.lng], { icon: icon }).addTo(map).bindPopup(popup);

  var li = document.createElement('li');
  li.innerHTML =
    '<div class="tx-date">' + m.date + '</div>' +
    '<div class="tx-price">' + m.price_label +
      '<span class="badge" style="background:#1a73e8;color:#fff">' + m.pyeong + '평</span>' +
      '<span class="badge" style="background:#eee;color:#555">' + m.price_per_pyeong.toLocaleString() + '만/평</span>' +
    '</div>' +
    '<div class="tx-info">' + m.address + (m.building_name ? ' · ' + m.building_name : '') + '</div>';

  li.addEventListener('click', function() {
    map.setView([m.lat, m.lng], 15);
    marker.openPopup();
  });
  list.appendChild(li);
});
</script>
</body>
</html>
"""

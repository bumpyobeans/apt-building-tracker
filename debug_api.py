import requests, xmltodict

KEY = '2093084e6f12cc232fbd0ddf5085292c9e5a274d1513962b9ef542e53e9aaa6b'
r = requests.get(
    'https://apis.data.go.kr/1613000/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade',
    params={'LAWD_CD': '41360', 'DEAL_YMD': '202503', 'serviceKey': KEY, 'numOfRows': 10, 'pageNo': 1},
    timeout=15
)
d = xmltodict.parse(r.text)
items = d['response']['body']['items']['item']
if isinstance(items, dict):
    items = [items]

print(f'총 {len(items)}건 샘플:')
for it in items[:5]:
    print({k: v for k, v in it.items()})
    print()

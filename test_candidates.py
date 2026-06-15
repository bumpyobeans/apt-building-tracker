import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
ROOT = os.path.dirname(os.path.abspath(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, '.env'))
import yaml
from molit_api import fetch_candidates

with open(os.path.join(ROOT, 'config.yaml'), encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

c = cfg['candidates']
key = os.environ['MOLIT_API_KEY']
results = fetch_candidates(
    c['lawd_codes'], key, c['months_back'],
    c['min_land_area_m2'], c['building_use_keywords']
)
print(f'후보 건물: {len(results)}건')
for r in results[:10]:
    print(f"  {r['date']} | {r['address']} | {r['pyeong']}평 | {r['price_man']:,}만원 | {r['building_name']}")

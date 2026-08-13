"""共用常數與路徑設定。"""
from pathlib import Path

# 591 端點
BASE_URL = "https://rent.591.com.tw"
LIST_URL = f"{BASE_URL}/list"

# 多排序聯集法用的排序清單（同一條件用多種 sort 各抓一次取聯集）
SORTS = ["posttime_desc", "money_asc", "money_desc", "area_asc", "area_desc"]

# 逐區查詢時每個區用的排序（單區通常 <30 筆，posttime 一次即可涵蓋；
# money_asc 補漏防單區超過 30 筆時漏抓）
SECTION_SORTS = ["posttime_desc", "money_asc"]

# 城市代碼 → 名稱
REGION_NAMES = {"1": "台北市", "3": "新北市"}

# 類型代碼 → 名稱（591 列表頁的 kind_name 文字）
KIND_NAMES = {"1": "整層住家", "2": "獨立套房", "3": "分租套房", "4": "雅房"}

# 反爬：請求間隔與重試
REQUEST_INTERVAL_SEC = 3
REQUEST_TIMEOUT_SEC = 20
MAX_RETRIES = 3  # 591 對機房 IP 偶發 403，多給幾次重試較能撐過
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

# 路徑
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
LATEST_PATH = DATA_DIR / "latest.json"
SUBSCRIPTIONS_PATH = ROOT / "subscriptions.json"
WATCHLIST_PATH = ROOT / "watchlist.json"

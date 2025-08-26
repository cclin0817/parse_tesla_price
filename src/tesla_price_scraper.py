#!/home/cclin/.local/python311/bin/python3
#!/home/cclin/.local/python311/bin/python3
"""
Tesla 台灣認證中古車爬蟲 - 完整動態載入版本
修正：處理虛擬滾動，收集所有出現過的車輛資料
"""

import time
import json
import sqlite3
from datetime import datetime
import logging
import re
import random
from typing import List, Dict, Optional, Set

# 先導入 selenium webdriver（一定需要）
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options

# 使用 undetected-chromedriver 來繞過檢測
try:
    import undetected_chromedriver as uc
    USE_UC = True
except ImportError:
    print("建議安裝 undetected-chromedriver: pip install undetected-chromedriver")
    USE_UC = False

# 嘗試導入 selenium-stealth
try:
    from selenium_stealth import stealth
    HAS_STEALTH = True
except ImportError:
    print("建議安裝 selenium-stealth: pip install selenium-stealth")
    HAS_STEALTH = False

import requests

# 嘗試導入 fake_useragent
try:
    from fake_useragent import UserAgent
    HAS_FAKE_UA = True
except ImportError:
    print("建議安裝 fake-useragent: pip install fake-useragent")
    HAS_FAKE_UA = False

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tesla_scraper_debug.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TeslaPriceScraper:
    """Tesla 完整動態載入爬蟲 - 處理虛擬滾動"""

    def __init__(self, db_path: str = "tesla_prices.db", debug_mode: bool = False):
        self.db_path = db_path
        self.debug_mode = debug_mode

        # 初始化 User Agent
        if HAS_FAKE_UA:
            try:
                self.ua = UserAgent()
            except:
                self.ua = None
        else:
            self.ua = None

        # Tesla台灣網站URL
        self.base_urls = {
            'model3': 'https://www.tesla.com/zh_tw/inventory/used/m3',
            'modely': 'https://www.tesla.com/zh_tw/inventory/used/my',
            'models': 'https://www.tesla.com/zh_tw/inventory/used/ms',
            'modelx': 'https://www.tesla.com/zh_tw/inventory/used/mx'
        }

        self.init_database()

    def init_database(self):
        """初始化資料庫"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicle_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vin TEXT,
                model TEXT,
                year INTEGER,
                trim TEXT,
                price INTEGER,
                mileage INTEGER,
                location TEXT,
                exterior_color TEXT,
                interior_color TEXT,
                autopilot_type TEXT,
                scrape_datetime DATETIME,
                listing_url TEXT,
                raw_data TEXT,
                UNIQUE(vin, scrape_datetime)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vin TEXT,
                model TEXT,
                price INTEGER,
                price_change INTEGER,
                change_percentage REAL,
                date_recorded DATE,
                UNIQUE(vin, date_recorded)
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("資料庫初始化完成")

    def get_random_user_agent(self):
        """獲取隨機 User Agent"""
        if self.ua:
            return self.ua.random

        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0'
        ]
        return random.choice(user_agents)

    def setup_driver(self, headless: bool = False):
        """
        設定增強版 WebDriver

        Args:
            headless: 是否使用無頭模式

        Returns:
            WebDriver 實例
        """
        if USE_UC:
            # 使用 undetected-chromedriver
            logger.info("使用 undetected-chromedriver...")

            options = uc.ChromeOptions()

            # 基本設定
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument(f'user-agent={self.get_random_user_agent()}')

            # 視窗設定
            if headless and not self.debug_mode:
                options.add_argument('--headless=new')  # 使用新版 headless 模式

            options.add_argument('--window-size=1920,1080')
            options.add_argument('--start-maximized')

            # 停用可能觸發檢測的功能
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=VizDisplayCompositor')
            options.add_argument('--disable-extensions')

            # 語言設定
            options.add_argument('--lang=zh-TW')

            # 創建 driver
            driver = uc.Chrome(options=options, version_main=None)

        else:
            # 使用標準 Selenium
            logger.info("使用標準 Selenium WebDriver...")

            options = Options()

            if headless and not self.debug_mode:
                options.add_argument('--headless')

            # 反檢測設定
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument(f'user-agent={self.get_random_user_agent()}')
            options.add_argument('--window-size=1920,1080')

            driver = webdriver.Chrome(options=options)

            # 執行反檢測腳本
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['zh-TW', 'zh', 'en']
                    });
                    window.chrome = {
                        runtime: {}
                    };
                    Object.defineProperty(navigator, 'permissions', {
                        get: () => ({
                            query: () => Promise.resolve({ state: 'granted' })
                        })
                    });
                '''
            })

        # 應用 selenium-stealth（如果可用）
        if HAS_STEALTH and not USE_UC:
            stealth(driver,
                languages=["zh-TW", "zh", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )

        return driver

    def wait_and_solve_challenge(self, driver):
        """等待並嘗試解決可能的挑戰（如 Cloudflare）"""
        logger.info("檢查是否有安全挑戰...")

        # 等待頁面載入
        time.sleep(random.uniform(3, 5))

        # 檢查是否有 Cloudflare 挑戰
        page_source = driver.page_source.lower()

        if 'checking your browser' in page_source or 'cloudflare' in page_source:
            logger.info("偵測到 Cloudflare 挑戰，等待通過...")
            time.sleep(10)  # 等待挑戰完成

        if 'access denied' in page_source or 'akamai' in page_source.lower():
            logger.warning("偵測到 Akamai 阻擋，嘗試重新載入...")

            # 清除 cookies 並重新載入
            driver.delete_all_cookies()
            time.sleep(random.uniform(2, 4))
            driver.refresh()
            time.sleep(random.uniform(5, 8))

    def scroll_and_collect_vehicles(self, driver, model: str) -> List[Dict]:
        """
        滾動頁面並收集所有出現過的車輛（處理虛擬滾動）

        Args:
            driver: WebDriver 實例
            model: 車型

        Returns:
            List[Dict]: 所有收集到的車輛資料
        """
        logger.info("開始滾動並收集車輛資料...")

        # 使用 Set 儲存已見過的車輛（根據唯一識別碼去重）
        collected_vehicles = {}  # 使用 dict，key 為唯一識別碼
        no_new_vehicles_count = 0
        last_count = 0

        # 首先滾動到頂部
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)

        # 最多滾動次數
        max_scrolls = 100

        for scroll_count in range(max_scrolls):
            # 收集當前可見的車輛
            current_batch = self.collect_visible_vehicles(driver, model)

            # 將新車輛加入到總集合中
            new_vehicles_count = 0
            for vehicle in current_batch:
                # 使用 VIN 或其他唯一識別碼作為 key
                unique_key = vehicle.get('vin') or vehicle.get('unique_id') or str(vehicle)
                if unique_key and unique_key not in collected_vehicles:
                    collected_vehicles[unique_key] = vehicle
                    new_vehicles_count += 1

            current_total = len(collected_vehicles)
            logger.info(f"滾動 {scroll_count + 1}/{max_scrolls}: 累計收集 {current_total} 輛車 (本次新增 {new_vehicles_count} 輛)")

            # 檢查是否有新車輛
            if current_total == last_count:
                no_new_vehicles_count += 1
                # 連續5次沒有新車輛，可能已經載入完畢
                if no_new_vehicles_count >= 5:
                    logger.info(f"已載入所有車輛，共收集 {current_total} 輛")
                    break
            else:
                no_new_vehicles_count = 0
                last_count = current_total

            # 執行滾動
            self.smart_scroll(driver, scroll_count)

            # 等待新內容載入
            time.sleep(random.uniform(2, 4))

            # 每10次滾動做一次額外檢查
            if scroll_count % 10 == 9:
                # 快速滾動到底再回來，觸發更多載入
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(2)

        # 最後再檢查一次
        final_batch = self.collect_visible_vehicles(driver, model)
        for vehicle in final_batch:
            unique_key = vehicle.get('vin') or vehicle.get('unique_id') or str(vehicle)
            if unique_key and unique_key not in collected_vehicles:
                collected_vehicles[unique_key] = vehicle

        # 轉換為列表返回
        result = list(collected_vehicles.values())
        logger.info(f"滾動完成，最終收集 {len(result)} 輛車")

        return result

    def collect_visible_vehicles(self, driver, model: str) -> List[Dict]:
        """
        收集當前可見的車輛資料

        Args:
            driver: WebDriver 實例
            model: 車型

        Returns:
            List[Dict]: 當前可見的車輛資料
        """
        vehicles = []

        # 多個可能的選擇器
        selectors = [
            "article.result.card",
            "article.result",
            "div.result-container",
            "article[class*='result']",
            "div[class*='vehicle']",
            ".tds-card",
            "[data-id]",
            "[data-vin]",
            "article[data-vin]",
            "div[data-id]"
        ]

        elements_found = False
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    logger.debug(f"使用選擇器 {selector} 找到 {len(elements)} 個元素")

                    for element in elements:
                        try:
                            # 檢查元素是否可見
                            if not element.is_displayed():
                                continue

                            # 解析車輛資料
                            vehicle_data = self.parse_vehicle_element_enhanced(element, model)
                            if vehicle_data:
                                vehicles.append(vehicle_data)
                                elements_found = True
                        except StaleElementReferenceException:
                            # 元素已經不在 DOM 中，跳過
                            continue
                        except Exception as e:
                            logger.debug(f"解析元素失敗: {e}")
                            continue

                    if elements_found:
                        break
            except Exception as e:
                logger.debug(f"選擇器 {selector} 失敗: {e}")
                continue

        # 如果標準選擇器都失敗，嘗試更廣泛的搜尋
        if not vehicles:
            try:
                # 嘗試找所有包含價格資訊的元素
                all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'NT$') or contains(text(), 'TWD')]/..")
                logger.debug(f"廣泛搜尋找到 {len(all_elements)} 個可能的元素")

                for element in all_elements[:50]:  # 限制處理數量避免過慢
                    try:
                        vehicle_data = self.parse_vehicle_element_enhanced(element, model)
                        if vehicle_data:
                            vehicles.append(vehicle_data)
                    except:
                        continue
            except:
                pass

        return vehicles

    def smart_scroll(self, driver, iteration: int):
        """
        智能滾動策略

        Args:
            driver: WebDriver 實例
            iteration: 當前滾動次數
        """
        # 獲取頁面資訊
        page_height = driver.execute_script("return document.body.scrollHeight")
        window_height = driver.execute_script("return window.innerHeight")
        current_position = driver.execute_script("return window.pageYOffset")

        # 根據迭代次數使用不同策略
        if iteration % 3 == 0:
            # 每3次做一次大幅滾動
            target = min(current_position + window_height * 2, page_height)
        elif iteration % 3 == 1:
            # 小幅滾動
            target = min(current_position + window_height * 0.5, page_height)
        else:
            # 中幅滾動
            target = min(current_position + window_height, page_height)

        # 如果已經到底，回滾一點再繼續
        if current_position >= page_height - window_height:
            target = page_height * 0.7

        # 平滑滾動
        driver.execute_script(f"""
            window.scrollTo({{
                top: {target},
                behavior: 'smooth'
            }});
        """)

    def parse_vehicle_element_enhanced(self, element, model: str) -> Optional[Dict]:
        """
        增強版車輛元素解析

        Args:
            element: WebElement
            model: 車型

        Returns:
            Optional[Dict]: 解析後的車輛資料
        """
        try:
            # 獲取元素文字
            text = element.text
            if not text or len(text) < 10:
                return None

            # 基本資料結構
            data = {
                'model': model.upper(),
                'scrape_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # 嘗試獲取 data 屬性
            try:
                data_vin = element.get_attribute('data-vin')
                if data_vin:
                    data['vin'] = data_vin

                data_id = element.get_attribute('data-id')
                if data_id:
                    data['unique_id'] = data_id
            except:
                pass

            # 提取價格（必要欄位）
            price_patterns = [
                r'NT\$\s*([\d,]+)',
                r'TWD\s*([\d,]+)',
                r'NTD\s*([\d,]+)',
                r'\$\s*([\d,]+)',
                r'([\d,]+)\s*元',
                r'售價[：:]\s*([\d,]+)',
                r'Price[：:]\s*([\d,]+)'
            ]

            price_found = False
            for pattern in price_patterns:
                price_match = re.search(pattern, text, re.IGNORECASE)
                if price_match:
                    price_str = price_match.group(1).replace(',', '')
                    price = int(price_str)
                    # 檢查價格是否合理（10萬到1000萬之間）
                    if 100000 <= price <= 10000000:
                        data['price'] = price
                        price_found = True
                        break

            # 如果沒有價格，這可能不是車輛元素
            if not price_found:
                return None

            # 提取 VIN（如果還沒有）
            if 'vin' not in data:
                vin_match = re.search(r'5YJ[A-Z0-9]{14}', text)
                if vin_match:
                    data['vin'] = vin_match.group()
                else:
                    # 生成唯一ID（使用價格和部分文字的hash）
                    import hashlib
                    unique_text = f"{model}_{data['price']}_{text[:50]}"
                    data['unique_id'] = hashlib.md5(unique_text.encode()).hexdigest()[:12]

            # 提取年份
            year_patterns = [
                r'(20[12][0-9])\s*年',
                r'Year[：:]\s*(20[12][0-9])',
                r'(20[12][0-9])\s+Model',
                r'(20[12][0-9])'
            ]

            for pattern in year_patterns:
                year_match = re.search(pattern, text)
                if year_match:
                    year = int(year_match.group(1))
                    if 2010 <= year <= 2025:
                        data['year'] = year
                        break

            # 提取里程
            mileage_patterns = [
                r'([\d,]+)\s*(?:km|公里|KM)',
                r'里程[：:]\s*([\d,]+)',
                r'Mileage[：:]\s*([\d,]+)',
                r'ODO[：:]\s*([\d,]+)'
            ]

            for pattern in mileage_patterns:
                mileage_match = re.search(pattern, text, re.IGNORECASE)
                if mileage_match:
                    mileage_str = mileage_match.group(1).replace(',', '')
                    mileage = int(mileage_str)
                    # 檢查里程是否合理（0到50萬公里）
                    if 0 <= mileage <= 500000:
                        data['mileage'] = mileage
                        break

            # 提取地點
            locations = [
                '台北', '新北', '桃園', '台中', '台南', '高雄',
                '基隆', '新竹', '苗栗', '彰化', '南投', '雲林',
                '嘉義', '屏東', '宜蘭', '花蓮', '台東', '澎湖',
                '金門', '連江', 'Taipei', 'Taichung', 'Kaohsiung'
            ]

            for location in locations:
                if location in text:
                    data['location'] = location
                    break

            # 提取顏色
            colors = {
                'Pearl White': '珍珠白',
                'Solid Black': '純黑',
                'Midnight Silver': '午夜銀',
                'Deep Blue': '深藍',
                'Red': '紅色',
                '珍珠白': '珍珠白',
                '純黑': '純黑',
                '午夜銀': '午夜銀',
                '深藍': '深藍',
                '紅色': '紅色'
            }

            for eng, chi in colors.items():
                if eng in text or chi in text:
                    data['exterior_color'] = chi
                    break

            # 提取配置
            if 'Long Range' in text or '長續航' in text:
                data['trim'] = 'Long Range'
            elif 'Performance' in text or '高性能' in text:
                data['trim'] = 'Performance'
            elif 'Standard' in text or '標準' in text:
                data['trim'] = 'Standard Range'

            # 嘗試獲取連結
            try:
                links = element.find_elements(By.TAG_NAME, "a")
                for link in links:
                    href = link.get_attribute('href')
                    if href and 'tesla.com' in href:
                        data['listing_url'] = href
                        break
            except:
                pass

            # 儲存原始資料（限制長度）
            data['raw_data'] = text[:500]

            return data

        except Exception as e:
            logger.debug(f"解析元素失敗: {e}")
            return None

    def scrape_with_retry(self, model: str, max_retries: int = 3) -> List[Dict]:
        """
        使用重試機制爬取資料
        """
        for attempt in range(max_retries):
            logger.info(f"嘗試爬取 {model} (第 {attempt + 1}/{max_retries} 次)")

            try:
                vehicles = self.scrape_with_selenium(model)
                if vehicles:
                    return vehicles

                logger.warning(f"第 {attempt + 1} 次嘗試未獲取到資料")

            except Exception as e:
                logger.error(f"第 {attempt + 1} 次嘗試失敗: {e}")

            if attempt < max_retries - 1:
                wait_time = random.uniform(10, 20) * (attempt + 1)
                logger.info(f"等待 {wait_time:.1f} 秒後重試...")
                time.sleep(wait_time)

        return []

    def scrape_with_selenium(self, model: str) -> List[Dict]:
        """
        使用 Selenium 爬取資料（處理虛擬滾動）
        """
        if model not in self.base_urls:
            logger.error(f"不支援的車型: {model}")
            return []

        url = self.base_urls[model]
        vehicles = []
        driver = None

        try:
            # 設定 driver
            driver = self.setup_driver(headless=False)  # 建議先用非 headless 模式

            logger.info(f"訪問 URL: {url}")

            # 第一步：先訪問主頁建立 session
            logger.info("先訪問 Tesla 主頁...")
            driver.get("https://www.tesla.com/zh_tw")
            time.sleep(random.uniform(3, 5))

            # 第二步：訪問目標頁面
            logger.info(f"訪問目標頁面: {url}")
            driver.get(url)

            # 等待並處理可能的挑戰
            self.wait_and_solve_challenge(driver)

            # 等待初始內容載入
            time.sleep(random.uniform(5, 8))

            # 重要：使用新的滾動收集方法
            vehicles = self.scroll_and_collect_vehicles(driver, model)

            # 截圖（偵錯用）
            if self.debug_mode:
                driver.save_screenshot(f'debug_{model}_final.png')
                logger.info(f"已儲存截圖: debug_{model}_final.png")

                # 儲存收集到的資料
                with open(f'debug_{model}_vehicles.json', 'w', encoding='utf-8') as f:
                    json.dump(vehicles, f, ensure_ascii=False, indent=2, default=str)
                logger.info(f"已儲存車輛資料: debug_{model}_vehicles.json")

            logger.info(f"成功收集 {len(vehicles)} 輛車的資料")

        except Exception as e:
            logger.error(f"Selenium 爬取失敗: {e}")
            if driver and self.debug_mode:
                driver.save_screenshot(f'error_{model}_{int(time.time())}.png')

        finally:
            if driver:
                driver.quit()

        return vehicles

    def run(self):
        """執行主程式"""
        logger.info("\n" + "="*60)
        logger.info("開始執行 Tesla 完整動態載入爬蟲")
        logger.info("="*60)

        all_vehicles = []

        for model in self.base_urls.keys():
            logger.info(f"\n處理 {model.upper()}")

            # 使用重試機制
            vehicles = self.scrape_with_retry(model)

            if vehicles:
                all_vehicles.extend(vehicles)
                logger.info(f"✅ {model.upper()} 獲取 {len(vehicles)} 筆資料")
            else:
                logger.warning(f"⚠️ {model.upper()} 未獲取到資料")

            # 隨機延遲，避免請求過快
            if model != list(self.base_urls.keys())[-1]:
                wait_time = random.uniform(15, 30)
                logger.info(f"等待 {wait_time:.1f} 秒...")
                time.sleep(wait_time)

        # 儲存資料
        if all_vehicles:
            self.save_to_database(all_vehicles)
            logger.info(f"\n✅ 總共獲取 {len(all_vehicles)} 筆資料")
            self.print_summary(all_vehicles)
        else:
            logger.warning("\n⚠️ 未獲取到任何資料")
            self.suggest_alternative_methods()

    def print_summary(self, vehicles: List[Dict]):
        """列印爬取結果摘要"""
        logger.info("\n" + "="*60)
        logger.info("爬取結果摘要")
        logger.info("="*60)

        # 統計各車型數量
        model_counts = {}
        for vehicle in vehicles:
            model = vehicle.get('model', 'Unknown')
            model_counts[model] = model_counts.get(model, 0) + 1

        for model, count in model_counts.items():
            logger.info(f"{model}: {count} 輛")

        # 統計價格範圍
        prices = [v['price'] for v in vehicles if 'price' in v]
        if prices:
            logger.info(f"\n價格範圍: NT${min(prices):,} - NT${max(prices):,}")
            logger.info(f"平均價格: NT${sum(prices)/len(prices):,.0f}")

        # 顯示部分 VIN 以確認資料
        vins = [v.get('vin', v.get('unique_id', 'N/A'))[:10] for v in vehicles[:5]]
        logger.info(f"\n前5筆資料識別碼: {', '.join(vins)}")

    def suggest_alternative_methods(self):
        """建議替代方法"""
        logger.info("\n" + "="*60)
        logger.info("替代方案建議：")
        logger.info("="*60)
        logger.info("""
1. 使用代理伺服器:
   - 使用住宅代理 (Residential Proxy)
   - 使用 VPN 服務

2. 使用 Playwright:
   pip install playwright
   playwright install chromium

3. 使用 DrissionPage (更強大的反檢測):
   pip install DrissionPage

4. 監控網路請求:
   - 使用瀏覽器開發者工具查看 API 端點
   - 直接請求 API 獲取資料

5. 半自動方案:
   - 手動登入後再執行爬蟲
   - 使用瀏覽器擴充功能輔助
        """)

    def save_to_database(self, vehicles: List[Dict]):
        """儲存到資料庫"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        saved_count = 0
        for vehicle in vehicles:
            try:
                # 使用 VIN 或 unique_id 作為識別
                vin = vehicle.get('vin') or vehicle.get('unique_id')

                cursor.execute('''
                    INSERT OR REPLACE INTO vehicle_prices
                    (vin, model, year, trim, price, mileage, location,
                     exterior_color, interior_color, autopilot_type,
                     scrape_datetime, listing_url, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    vin,
                    vehicle.get('model'),
                    vehicle.get('year'),
                    vehicle.get('trim'),
                    vehicle.get('price'),
                    vehicle.get('mileage'),
                    vehicle.get('location'),
                    vehicle.get('exterior_color'),
                    vehicle.get('interior_color'),
                    vehicle.get('autopilot_type'),
                    vehicle.get('scrape_datetime'),
                    vehicle.get('listing_url'),
                    vehicle.get('raw_data', '')
                ))
                saved_count += 1
            except Exception as e:
                logger.error(f"儲存失敗: {e}")

        conn.commit()
        conn.close()

        logger.info(f"成功儲存 {saved_count}/{len(vehicles)} 筆資料到資料庫")

def main():
    """主程式"""
    print("\n" + "="*60)
    print("Tesla 完整動態載入爬蟲")
    print("="*60)

    # 檢查必要套件
    print("\n檢查必要套件...")

    required_packages = {
        'undetected-chromedriver': USE_UC,
        'selenium-stealth': HAS_STEALTH,
        'fake-useragent': HAS_FAKE_UA
    }

    missing_packages = [pkg for pkg, installed in required_packages.items() if not installed]

    if missing_packages:
        print("\n建議安裝以下套件以獲得最佳效果：")
        print(f"pip install {' '.join(missing_packages)}")
        print("\n是否繼續？(y/n): ", end='')

        if input().lower() != 'y':
            print("已取消")
            return

    # 執行爬蟲
    scraper = TeslaPriceScraper(debug_mode=True)
    scraper.run()

if __name__ == "__main__":
    main()

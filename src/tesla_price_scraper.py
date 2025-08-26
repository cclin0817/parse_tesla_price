#!/home/cclin/.local/python311/bin/python3
"""
Tesla 台灣認證中古車爬蟲 - 繞過 Akamai 防護版本
"""

import time
import json
import sqlite3
from datetime import datetime
import logging
import re
import random
from typing import List, Dict, Optional

# 先導入 selenium webdriver（一定需要）
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
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

class TeslaScraper:
    """Tesla 反反爬蟲增強版爬蟲"""

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

    def human_like_behavior(self, driver):
        """模擬人類行為"""
        # 隨機移動滑鼠
        action = ActionChains(driver)

        # 獲取頁面大小
        width = driver.execute_script("return window.innerWidth")
        height = driver.execute_script("return window.innerHeight")

        # 隨機移動滑鼠 3-5 次
        for _ in range(random.randint(3, 5)):
            x = random.randint(100, width - 100)
            y = random.randint(100, height - 100)

            action.move_by_offset(x, y)
            action.pause(random.uniform(0.1, 0.3))

        try:
            action.perform()
        except:
            pass

        # 隨機捲動
        scroll_times = random.randint(2, 4)
        for _ in range(scroll_times):
            scroll_amount = random.randint(100, 300)
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(0.5, 1.5))

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
        使用 Selenium 爬取資料（增強版）
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

            # 模擬人類行為
            self.human_like_behavior(driver)

            # 第二步：訪問目標頁面
            logger.info(f"訪問目標頁面: {url}")
            driver.get(url)

            # 等待並處理可能的挑戰
            self.wait_and_solve_challenge(driver)

            # 模擬人類行為
            self.human_like_behavior(driver)

            # 等待頁面載入
            wait = WebDriverWait(driver, 30)

            # 截圖（偵錯用）
            if self.debug_mode:
                driver.save_screenshot(f'debug_{model}_final.png')
                logger.info(f"已儲存截圖: debug_{model}_final.png")

                # 儲存頁面源碼
                with open(f'debug_{model}_source.html', 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                logger.info(f"已儲存頁面源碼: debug_{model}_source.html")

            # 檢查是否被阻擋
            if 'access denied' in driver.page_source.lower():
                logger.error("仍然被阻擋，可能需要其他方法")
                return []

            # 嘗試解析頁面
            vehicles = self.extract_vehicles_from_page(driver, model)

        except Exception as e:
            logger.error(f"Selenium 爬取失敗: {e}")
            if driver and self.debug_mode:
                driver.save_screenshot(f'error_{model}_{int(time.time())}.png')

        finally:
            if driver:
                driver.quit()

        return vehicles

    def extract_vehicles_from_page(self, driver, model: str) -> List[Dict]:
        """從頁面提取車輛資料"""
        vehicles = []

        # 等待可能的車輛卡片載入
        time.sleep(5)

        # 嘗試各種可能的選擇器
        selectors = [
            "article.result",
            "div.result-container",
            "article[class*='result']",
            "div[class*='vehicle']",
            "[data-id]",
            "[data-vin]"
        ]

        vehicle_elements = []
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    logger.info(f"找到 {len(elements)} 個元素使用選擇器: {selector}")
                    vehicle_elements = elements
                    break
            except:
                continue

        if not vehicle_elements:
            logger.warning("未找到車輛元素")

            # 嘗試從 JavaScript 提取
            vehicles = self.extract_from_javascript_enhanced(driver)

        else:
            # 解析元素
            for element in vehicle_elements:
                try:
                    vehicle_data = self.parse_vehicle_element(element, model)
                    if vehicle_data:
                        vehicles.append(vehicle_data)
                except Exception as e:
                    logger.error(f"解析元素失敗: {e}")

        return vehicles

    def extract_from_javascript_enhanced(self, driver) -> List[Dict]:
        """增強版 JavaScript 資料提取"""
        logger.info("嘗試從 JavaScript 提取資料...")

        try:
            # 嘗試獲取 React/Next.js 資料
            result = driver.execute_script("""
                // 檢查各種可能的資料來源
                if (window.__NEXT_DATA__) {
                    return window.__NEXT_DATA__;
                }
                if (window.__INITIAL_STATE__) {
                    return window.__INITIAL_STATE__;
                }

                // 檢查 React 元件的 props
                const root = document.querySelector('#root') || document.querySelector('#__next');
                if (root && root._reactRootContainer) {
                    return root._reactRootContainer;
                }

                // 查找包含車輛資料的全域變數
                for (let key in window) {
                    if (key.toLowerCase().includes('inventory') ||
                        key.toLowerCase().includes('vehicle') ||
                        key.toLowerCase().includes('data')) {
                        const value = window[key];
                        if (value && typeof value === 'object' &&
                            (Array.isArray(value) || value.results || value.vehicles)) {
                            return {found: key, data: value};
                        }
                    }
                }

                return null;
            """)

            if result:
                logger.info(f"找到 JavaScript 資料: {type(result)}")
                # 這裡需要根據實際的資料結構來解析
                # 可以將結果寫入檔案分析結構
                if self.debug_mode:
                    with open('debug_js_data.json', 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
                    logger.info("JavaScript 資料已儲存到 debug_js_data.json")

        except Exception as e:
            logger.error(f"JavaScript 提取失敗: {e}")

        return []

    def parse_vehicle_element(self, element, model: str) -> Optional[Dict]:
        """解析車輛元素"""
        try:
            data = {
                'model': model.upper(),
                'scrape_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # 獲取所有文字
            text = element.text

            # 提取價格
            price_match = re.search(r'(?:NT\$|TWD|NTD)\s*([\d,]+)', text)
            if price_match:
                data['price'] = int(price_match.group(1).replace(',', ''))

            # 提取 VIN
            vin_match = re.search(r'5YJ[A-Z0-9]{14}', text)
            if vin_match:
                data['vin'] = vin_match.group()

            # 提取年份
            year_match = re.search(r'20(1[0-9]|2[0-4])', text)
            if year_match:
                data['year'] = int(year_match.group())

            # 提取里程
            mileage_match = re.search(r'([\d,]+)\s*(?:km|公里)', text, re.IGNORECASE)
            if mileage_match:
                data['mileage'] = int(mileage_match.group(1).replace(',', ''))

            # 獲取連結
            try:
                link = element.find_element(By.TAG_NAME, "a")
                data['listing_url'] = link.get_attribute('href')
            except:
                pass

            data['raw_data'] = text[:500]

            return data if 'price' in data else None

        except Exception as e:
            logger.error(f"解析元素失敗: {e}")
            return None

    def run(self):
        """執行主程式"""
        logger.info("\n" + "="*60)
        logger.info("開始執行 Tesla 反反爬蟲增強版爬蟲")
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
        else:
            logger.warning("\n⚠️ 未獲取到任何資料")
            self.suggest_alternative_methods()

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

4. 手動解決:
   - 使用瀏覽器擴充功能匯出資料
   - 使用瀏覽器開發者工具監控 API 請求

5. API 方法:
   - 尋找 Tesla 的官方 API
   - 使用第三方資料服務
        """)

    def save_to_database(self, vehicles: List[Dict]):
        """儲存到資料庫"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for vehicle in vehicles:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO vehicle_prices
                    (vin, model, year, trim, price, mileage, location,
                     exterior_color, interior_color, autopilot_type,
                     scrape_datetime, listing_url, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    vehicle.get('vin'),
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
            except Exception as e:
                logger.error(f"儲存失敗: {e}")

        conn.commit()
        conn.close()

def main():
    """主程式"""
    print("\n" + "="*60)
    print("Tesla 反反爬蟲增強版爬蟲")
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
    scraper = TeslaScraper(debug_mode=True)
    scraper.run()

if __name__ == "__main__":
    main()

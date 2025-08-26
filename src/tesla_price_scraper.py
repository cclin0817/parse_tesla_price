#!/home/cclin/.local/python311/bin/python3
"""
Tesla 台灣認證中古車爬蟲 - 增強版
解決動態載入和解析問題
"""

import time
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import logging
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests

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
    """Tesla增強版爬蟲"""

    def __init__(self, db_path: str = "tesla_prices.db", debug_mode: bool = True):
        """
        初始化爬蟲

        Args:
            db_path: 資料庫路徑
            debug_mode: 是否啟用偵錯模式
        """
        self.db_path = db_path
        self.debug_mode = debug_mode

        # Tesla台灣網站URL
        self.base_urls = {
            'model3': 'https://www.tesla.com/zh_tw/inventory/used/m3',
            'modely': 'https://www.tesla.com/zh_tw/inventory/used/my',
            'models': 'https://www.tesla.com/zh_tw/inventory/used/ms',
            'modelx': 'https://www.tesla.com/zh_tw/inventory/used/mx'
        }

        # API端點（備用方案）
        self.api_url = 'https://www.tesla.com/inventory/api/v1/inventory-results'

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

    def setup_driver(self, headless: bool = False) -> webdriver.Chrome:
        """
        設定Selenium WebDriver

        Args:
            headless: 是否使用無頭模式
        """
        options = Options()

        if headless:
            options.add_argument('--headless')

        # 基本設定
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # 設定視窗大小，確保所有元素都能載入
        options.add_argument('--window-size=1920,1080')

        # 設定User-Agent
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # 停用圖片載入以加快速度（可選）
        # prefs = {"profile.managed_default_content_settings.images": 2}
        # options.add_experimental_option("prefs", prefs)

        try:
            driver = webdriver.Chrome(options=options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return driver
        except Exception as e:
            logger.error(f"Chrome Driver初始化失敗: {e}")
            logger.info("嘗試使用webdriver-manager...")

            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service

                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                return driver
            except Exception as e2:
                logger.error(f"webdriver-manager也失敗: {e2}")
                raise

    def try_api_approach(self, model: str) -> List[Dict]:
        """
        嘗試使用API方式獲取資料

        Args:
            model: 車型代碼

        Returns:
            車輛資料列表
        """
        logger.info(f"嘗試使用API方式獲取 {model} 資料...")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Origin': 'https://www.tesla.com',
            'Referer': f'https://www.tesla.com/zh_tw/inventory/used/{model}'
        }

        params = {
            'query': json.dumps({
                'model': model,
                'condition': 'used',
                'options': {},
                'arrangeby': 'Price',
                'order': 'asc',
                'market': 'TW',
                'language': 'zh_TW',
                'super_region': 'asia pacific',
                'lng': 121.5654,  # 台北
                'lat': 25.0330,
                'zip': '100',
                'range': 0,
                'region': 'TW'
            }),
            'offset': 0,
            'count': 50,
            'outsideOffset': 0,
            'outsideSearch': False
        }

        try:
            response = requests.get(self.api_url, params=params, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                total = data.get('total_matches_found', 0)

                logger.info(f"API回應: 找到 {total} 輛車")

                vehicles = []
                for item in results:
                    vehicle = self.parse_api_response(item, model)
                    if vehicle:
                        vehicles.append(vehicle)

                return vehicles
            else:
                logger.warning(f"API回應狀態碼: {response.status_code}")

        except Exception as e:
            logger.error(f"API請求失敗: {e}")

        return []

    def parse_api_response(self, item: Dict, model: str) -> Optional[Dict]:
        """解析API回應"""
        try:
            return {
                'vin': item.get('VIN', item.get('vin')),
                'model': model.upper(),
                'year': item.get('Year', item.get('year')),
                'trim': item.get('TrimName', item.get('trim')),
                'price': item.get('Price', item.get('price')),
                'mileage': item.get('Odometer', item.get('odometer')),
                'location': item.get('MetroName', item.get('City', '台灣')),
                'exterior_color': item.get('PAINT', [None])[0] if isinstance(item.get('PAINT'), list) else item.get('PAINT'),
                'interior_color': item.get('INTERIOR', [None])[0] if isinstance(item.get('INTERIOR'), list) else item.get('INTERIOR'),
                'autopilot_type': item.get('AUTOPILOT', [None])[0] if isinstance(item.get('AUTOPILOT'), list) else item.get('AUTOPILOT'),
                'listing_url': f"https://www.tesla.com/zh_tw/{model}/{item.get('VIN')}",
                'scrape_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'raw_data': json.dumps(item)
            }
        except Exception as e:
            logger.error(f"解析API資料失敗: {e}")
            return None

    def scrape_with_selenium(self, model: str) -> List[Dict]:
        """
        使用Selenium爬取資料

        Args:
            model: 車型名稱

        Returns:
            車輛資料列表
        """
        if model not in self.base_urls:
            logger.error(f"不支援的車型: {model}")
            return []

        url = self.base_urls[model]
        vehicles = []
        driver = None

        try:
            # 使用非無頭模式進行偵錯
            driver = self.setup_driver(headless=not self.debug_mode)
            logger.info(f"開始爬取 {model} 的資料...")
            logger.info(f"URL: {url}")

            driver.get(url)

            # 等待頁面基本載入
            wait = WebDriverWait(driver, 20)

            # 截圖（偵錯用）
            if self.debug_mode:
                driver.save_screenshot(f'debug_{model}_initial.png')
                logger.info(f"已儲存初始截圖: debug_{model}_initial.png")

            # 等待並檢查是否需要接受cookie
            try:
                cookie_button = wait.until(EC.element_to_be_clickable((By.ID, "accept-cookies")))
                cookie_button.click()
                logger.info("已接受cookie")
            except:
                pass

            # 捲動頁面以觸發延遲載入
            logger.info("捲動頁面以載入更多內容...")
            for i in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)

            # 等待可能的載入動畫完成
            time.sleep(3)

            # 截圖（偵錯用）
            if self.debug_mode:
                driver.save_screenshot(f'debug_{model}_after_scroll.png')
                logger.info(f"已儲存捲動後截圖: debug_{model}_after_scroll.png")

            # 嘗試多種選擇器
            selectors = [
                # Tesla可能使用的選擇器
                "article.result-card",
                "div.result-card",
                "article[data-id]",
                "div[data-vin]",
                ".inventory-list-item",
                ".vehicle-card",
                ".tds-card",
                "article[class*='result']",
                "div[class*='vehicle']",
                "div[class*='inventory']",
                # 更通用的選擇器
                "main article",
                "main > div > article",
                "[role='article']",
                "a[href*='/inventory/']"
            ]

            vehicle_elements = []
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logger.info(f"使用選擇器 '{selector}' 找到 {len(elements)} 個元素")
                        vehicle_elements = elements
                        break
                except Exception as e:
                    continue

            # 如果還是找不到，嘗試獲取頁面HTML
            if not vehicle_elements:
                page_source = driver.page_source
                logger.info(f"頁面HTML長度: {len(page_source)}")

                # 儲存頁面原始碼（偵錯用）
                if self.debug_mode:
                    with open(f'debug_{model}_source.html', 'w', encoding='utf-8') as f:
                        f.write(page_source)
                    logger.info(f"已儲存頁面原始碼: debug_{model}_source.html")

                # 檢查是否有錯誤訊息或無車輛訊息
                if "沒有符合" in page_source or "no results" in page_source.lower():
                    logger.info(f"{model} 目前沒有庫存車輛")
                    return []

                # 嘗試從JavaScript變數中提取資料
                vehicles_from_js = self.extract_from_javascript(driver)
                if vehicles_from_js:
                    return vehicles_from_js

            # 解析找到的元素
            for element in vehicle_elements:
                try:
                    vehicle_data = self.extract_vehicle_data_enhanced(element, model, driver)
                    if vehicle_data:
                        vehicles.append(vehicle_data)
                        logger.info(f"成功提取車輛資訊: {vehicle_data.get('vin', 'Unknown')}")
                except Exception as e:
                    logger.error(f"提取車輛資料失敗: {e}")

        except TimeoutException:
            logger.error(f"頁面載入超時: {url}")
        except Exception as e:
            logger.error(f"Selenium爬取失敗: {e}")
        finally:
            if driver:
                driver.quit()

        return vehicles

    def extract_from_javascript(self, driver) -> List[Dict]:
        """從JavaScript變數中提取資料"""
        logger.info("嘗試從JavaScript變數提取資料...")

        try:
            # Tesla可能將資料存在window物件中
            result = driver.execute_script("""
                // 嘗試各種可能的資料位置
                if (window.__INITIAL_STATE__) return window.__INITIAL_STATE__;
                if (window.__NEXT_DATA__) return window.__NEXT_DATA__;
                if (window.Tesla && window.Tesla.inventory) return window.Tesla.inventory;
                if (window.inventoryData) return window.inventoryData;

                // 查找所有可能包含車輛資料的變數
                for (let key in window) {
                    if (key.includes('inventory') || key.includes('vehicle') || key.includes('data')) {
                        if (typeof window[key] === 'object' && window[key] !== null) {
                            return {key: key, data: window[key]};
                        }
                    }
                }
                return null;
            """)

            if result:
                logger.info(f"找到JavaScript資料: {type(result)}")
                # 這裡需要根據實際資料結構來解析
                return []

        except Exception as e:
            logger.error(f"JavaScript提取失敗: {e}")

        return []

    def extract_vehicle_data_enhanced(self, element, model: str, driver) -> Optional[Dict]:
        """
        增強版資料提取

        Args:
            element: 網頁元素
            model: 車型
            driver: WebDriver實例

        Returns:
            車輛資料
        """
        try:
            data = {
                'model': model.upper(),
                'scrape_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # 獲取元素的所有文字
            text_content = element.text
            logger.debug(f"元素文字內容: {text_content[:200]}...")

            # 提取價格（使用正則表達式）
            price_patterns = [
                r'NT\$\s*([\d,]+)',
                r'\$\s*([\d,]+)',
                r'([\d,]+)\s*元',
                r'([\d,]+\d{3})'  # 至少6位數字（價格通常是百萬級）
            ]

            for pattern in price_patterns:
                match = re.search(pattern, text_content)
                if match:
                    price_str = match.group(1).replace(',', '')
                    if price_str.isdigit():
                        price = int(price_str)
                        if price > 100000:  # 確保是合理的價格
                            data['price'] = price
                            break

            # 提取VIN
            vin_pattern = r'5YJ[A-Z0-9]{14}'
            vin_match = re.search(vin_pattern, text_content)
            if vin_match:
                data['vin'] = vin_match.group()
            else:
                # 使用時間戳作為臨時ID
                data['vin'] = f"TEMP_{model}_{int(time.time())}"

            # 提取年份
            year_pattern = r'20(1[0-9]|2[0-4])'
            year_match = re.search(year_pattern, text_content)
            if year_match:
                data['year'] = int(year_match.group())

            # 提取里程
            mileage_patterns = [
                r'([\d,]+)\s*km',
                r'([\d,]+)\s*公里',
                r'里程[：:]\s*([\d,]+)'
            ]

            for pattern in mileage_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    mileage_str = match.group(1).replace(',', '')
                    if mileage_str.isdigit():
                        data['mileage'] = int(mileage_str)
                        break

            # 獲取連結
            try:
                link = element.find_element(By.TAG_NAME, "a")
                data['listing_url'] = link.get_attribute('href')
            except:
                data['listing_url'] = None

            # 儲存原始文字
            data['raw_data'] = text_content[:1000]  # 只儲存前1000字

            return data if 'price' in data else None

        except Exception as e:
            logger.error(f"增強版資料提取失敗: {e}")
            return None

    def scrape_all_models(self) -> List[Dict]:
        """爬取所有車型"""
        all_vehicles = []

        for model in self.base_urls.keys():
            logger.info(f"\n{'='*50}")
            logger.info(f"開始處理 {model.upper()}")
            logger.info(f"{'='*50}")

            # 先嘗試API方式
            vehicles = self.try_api_approach(model)

            # 如果API失敗，使用Selenium
            if not vehicles:
                logger.info("API方式未獲取到資料，改用Selenium...")
                vehicles = self.scrape_with_selenium(model)

            if vehicles:
                all_vehicles.extend(vehicles)
                logger.info(f"✅ {model.upper()} 成功獲取 {len(vehicles)} 輛車資料")
            else:
                logger.warning(f"⚠️ {model.upper()} 未獲取到任何資料")

            # 避免請求過快
            time.sleep(3)

        return all_vehicles

    def save_to_database(self, vehicles: List[Dict]):
        """儲存到資料庫"""
        if not vehicles:
            logger.warning("沒有資料可儲存")
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        saved_count = 0
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
                saved_count += 1

            except Exception as e:
                logger.error(f"儲存資料失敗: {e}")

        conn.commit()
        conn.close()

        logger.info(f"✅ 成功儲存 {saved_count} 筆資料到資料庫")

    def run(self):
        """執行主程式"""
        logger.info("\n" + "="*60)
        logger.info("開始執行 Tesla 增強版爬蟲")
        logger.info("="*60)

        vehicles = self.scrape_all_models()

        if vehicles:
            self.save_to_database(vehicles)

            # 顯示摘要
            print("\n" + "="*60)
            print("爬取結果摘要")
            print("="*60)
            print(f"總共獲取: {len(vehicles)} 輛車資料")

            # 按車型分組統計
            from collections import Counter
            model_counts = Counter(v['model'] for v in vehicles)
            for model, count in model_counts.items():
                print(f"{model}: {count} 輛")

        else:
            logger.warning("\n⚠️ 未能獲取任何車輛資料")
            logger.info("\n可能的原因：")
            logger.info("1. Tesla台灣網站目前沒有認證中古車庫存")
            logger.info("2. 網站結構已更改，需要更新爬蟲程式")
            logger.info("3. 網路連線問題")
            logger.info("\n建議：")
            logger.info("1. 手動訪問 https://www.tesla.com/zh_tw/inventory/used/m3 確認是否有車輛")
            logger.info("2. 檢查 debug_*.png 截圖檔案查看實際頁面內容")
            logger.info("3. 查看 debug_*.html 檔案分析頁面結構")

def main():
    """主程式入口"""
    # 啟用偵錯模式
    scraper = TeslaScraper(debug_mode=True)
    scraper.run()

if __name__ == "__main__":
    main()

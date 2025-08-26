#!/home/cclin/.local/python311/bin/python3
#!/usr/bin/env python3
"""
Tesla 認證中古車價格追蹤系統 - 主程式
整合爬蟲、分析和視覺化功能
"""

import os
import sys
import sqlite3
import argparse
from datetime import datetime
import time

# 檢查必要套件
required_packages = {
    'selenium': 'selenium',
    'pandas': 'pandas',
    'matplotlib': 'matplotlib',
    'seaborn': 'seaborn',
    'requests': 'requests',
    'bs4': 'beautifulsoup4'
}

def check_requirements():
    """檢查必要套件是否已安裝"""
    missing_packages = []
    for module, package in required_packages.items():
        try:
            __import__(module)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print("❌ 缺少必要套件，請執行以下命令安裝：")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    return True

def check_database(db_path="tesla_prices.db"):
    """檢查資料庫狀態"""
    if not os.path.exists(db_path):
        print(f"❌ 資料庫不存在: {db_path}")
        return False, 0

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 檢查表格是否存在
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='vehicle_prices'
    """)

    if not cursor.fetchone():
        conn.close()
        print("❌ 資料庫表格不存在")
        return False, 0

    # 檢查資料筆數
    cursor.execute("SELECT COUNT(*) FROM vehicle_prices")
    count = cursor.fetchone()[0]
    conn.close()

    return True, count

def initialize_system():
    """初始化系統"""
    print("\n🚀 初始化Tesla價格追蹤系統...")

    # 檢查Chrome瀏覽器
    print("\n檢查Chrome瀏覽器...")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')

        try:
            driver = webdriver.Chrome(options=options)
            driver.quit()
            print("✅ Chrome瀏覽器設定正確")
        except Exception as e:
            print("⚠️ Chrome瀏覽器可能未正確安裝")
            print("請安裝Chrome瀏覽器和ChromeDriver")
            print("\n自動安裝ChromeDriver:")
            print("pip install webdriver-manager")
            print("\n然後在程式中使用:")
            print("from webdriver_manager.chrome import ChromeDriverManager")
            print("from selenium.webdriver.chrome.service import Service")
            print("service = Service(ChromeDriverManager().install())")
            print("driver = webdriver.Chrome(service=service)")
            return False
    except ImportError:
        print("❌ Selenium未安裝")
        return False

    return True

def run_simple_scraper():
    """執行簡化版爬蟲（用於測試）"""
    print("\n🔄 執行簡化版爬蟲...")

    import sqlite3
    import requests
    from datetime import datetime
    import random

    # 建立資料庫
    conn = sqlite3.connect("tesla_prices.db")
    cursor = conn.cursor()

    # 創建表格
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

    # 插入測試資料（模擬爬取的資料）
    print("插入模擬資料用於測試...")

    models = ['MODEL3', 'MODELY', 'MODELS', 'MODELX']
    colors = ['Pearl White', 'Solid Black', 'Midnight Silver', 'Deep Blue', 'Red']
    locations = ['台北', '新北', '桃園', '台中', '高雄']

    test_data = []
    for i in range(20):
        model = random.choice(models)
        base_price = {
            'MODEL3': 1800000,
            'MODELY': 2200000,
            'MODELS': 3500000,
            'MODELX': 4000000
        }[model]

        vehicle = (
            f"5YJ3{model[5]}{random.randint(10000, 99999)}",  # VIN
            model,
            random.choice([2021, 2022, 2023, 2024]),  # year
            'Long Range' if random.random() > 0.5 else 'Performance',  # trim
            base_price + random.randint(-200000, 300000),  # price
            random.randint(5000, 50000),  # mileage
            random.choice(locations),
            random.choice(colors),
            random.choice(['Black', 'White', 'Cream']),
            'Enhanced Autopilot',
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            f"https://www.tesla.com/inventory/{model.lower()}/demo"
        )
        test_data.append(vehicle)

    # 插入資料
    cursor.executemany('''
        INSERT OR IGNORE INTO vehicle_prices
        (vin, model, year, trim, price, mileage, location,
         exterior_color, interior_color, autopilot_type,
         scrape_datetime, listing_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', test_data)

    # 插入價格趨勢資料
    for vehicle in test_data:
        cursor.execute('''
            INSERT OR IGNORE INTO price_trends
            (vin, model, price, price_change, change_percentage, date_recorded)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            vehicle[0],  # vin
            vehicle[1],  # model
            vehicle[4],  # price
            random.randint(-50000, 50000),  # price_change
            random.uniform(-5, 5),  # change_percentage
            datetime.now().date()
        ))

    conn.commit()
    conn.close()

    print(f"✅ 成功插入 {len(test_data)} 筆測試資料")
    return True

def run_full_scraper():
    """執行完整爬蟲"""
    print("\n🔄 執行完整爬蟲...")

    try:
        from tesla_price_scraper import TeslaPriceScraper
        scraper = TeslaPriceScraper()
        scraper.run_scraper()
        return True
    except ImportError:
        print("❌ 找不到 tesla_price_scraper.py")
        print("使用簡化版爬蟲代替...")
        return run_simple_scraper()
    except Exception as e:
        print(f"❌ 爬蟲執行失敗: {e}")
        print("改用簡化版爬蟲...")
        return run_simple_scraper()

def run_visualization():
    """執行視覺化分析"""
    print("\n📊 執行視覺化分析...")

    try:
        from tesla_visualizer import TeslaPriceVisualizer
        visualizer = TeslaPriceVisualizer()
        visualizer.run_analysis()
        return True
    except ImportError:
        print("❌ 找不到 tesla_visualizer.py")
        print("執行簡化版分析...")
        return run_simple_analysis()
    except Exception as e:
        print(f"❌ 視覺化執行失敗: {e}")
        return False

def run_simple_analysis():
    """執行簡化版分析"""
    import pandas as pd
    import sqlite3

    conn = sqlite3.connect("tesla_prices.db")

    # 讀取資料
    df = pd.read_sql_query("SELECT * FROM vehicle_prices", conn)

    if df.empty:
        print("❌ 沒有資料可供分析")
        conn.close()
        return False

    # 基本統計
    print("\n" + "="*60)
    print("Tesla 認證中古車價格分析")
    print("="*60)

    print(f"\n📊 基本統計:")
    print(f"  總車輛數: {len(df)}")
    print(f"  平均價格: NT${df['price'].mean():,.0f}")
    print(f"  最低價格: NT${df['price'].min():,.0f}")
    print(f"  最高價格: NT${df['price'].max():,.0f}")

    print(f"\n🚗 各車型統計:")
    for model in df['model'].unique():
        model_df = df[df['model'] == model]
        print(f"\n  {model}:")
        print(f"    數量: {len(model_df)}")
        print(f"    平均價格: NT${model_df['price'].mean():,.0f}")
        print(f"    價格範圍: NT${model_df['price'].min():,.0f} - NT${model_df['price'].max():,.0f}")

    # 儲存報告
    df.to_csv('tesla_inventory_report.csv', index=False, encoding='utf-8-sig')
    print(f"\n✅ 報告已儲存至 tesla_inventory_report.csv")

    conn.close()
    return True

def show_menu():
    """顯示主選單"""
    print("\n" + "="*60)
    print("Tesla 認證中古車價格追蹤系統")
    print("="*60)

    # 檢查資料庫狀態
    db_exists, record_count = check_database()

    if db_exists:
        print(f"✅ 資料庫狀態: 正常 (包含 {record_count} 筆記錄)")
    else:
        print("⚠️ 資料庫狀態: 未初始化")

    print("\n請選擇功能:")
    print("1. 執行爬蟲 (爬取最新資料)")
    print("2. 查看分析報告")
    print("3. 生成視覺化圖表")
    print("4. 初始化系統 (首次使用)")
    print("5. 使用測試資料 (快速開始)")
    print("0. 結束")

    return input("\n請輸入選項 (0-5): ")

def main():
    """主程式"""
    parser = argparse.ArgumentParser(description='Tesla價格追蹤系統')
    parser.add_argument('--scrape', action='store_true', help='執行爬蟲')
    parser.add_argument('--analyze', action='store_true', help='執行分析')
    parser.add_argument('--test', action='store_true', help='使用測試資料')
    parser.add_argument('--auto', action='store_true', help='自動執行所有功能')

    args = parser.parse_args()

    # 檢查必要套件
    if not check_requirements():
        print("\n請先安裝必要套件後再執行程式")
        sys.exit(1)

    # 命令列模式
    if args.auto:
        print("🤖 自動模式啟動...")
        if not check_database()[0]:
            run_simple_scraper()
        run_simple_analysis()
        sys.exit(0)

    if args.test:
        run_simple_scraper()
        sys.exit(0)

    if args.scrape:
        run_full_scraper()
        sys.exit(0)

    if args.analyze:
        if not check_database()[0]:
            print("請先執行爬蟲或使用測試資料")
            sys.exit(1)
        run_visualization()
        sys.exit(0)

    # 互動式選單
    while True:
        choice = show_menu()

        if choice == '0':
            print("\n👋 感謝使用，再見！")
            break
        elif choice == '1':
            run_full_scraper()
        elif choice == '2':
            if check_database()[0]:
                run_simple_analysis()
            else:
                print("❌ 請先執行爬蟲或使用測試資料")
        elif choice == '3':
            if check_database()[0]:
                run_visualization()
            else:
                print("❌ 請先執行爬蟲或使用測試資料")
        elif choice == '4':
            if initialize_system():
                print("✅ 系統初始化成功")
            else:
                print("❌ 系統初始化失敗，請檢查錯誤訊息")
        elif choice == '5':
            run_simple_scraper()
            print("\n現在可以執行分析功能了！")
        else:
            print("❌ 無效的選項，請重新選擇")

        input("\n按Enter鍵繼續...")

if __name__ == "__main__":
    main()

#!/home/cclin/.local/python311/bin/python3
"""
Tesla 認證中古車價格趨勢視覺化分析
提供互動式圖表和深入的價格分析
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

# 設定中文字體
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

class TeslaPriceVisualizer:
    """Tesla價格視覺化分析工具"""

    def __init__(self, db_path: str = "tesla_prices.db"):
        """
        初始化視覺化工具

        Args:
            db_path: 資料庫路徑
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)

        # 設定Seaborn樣式
        sns.set_style("whitegrid")
        sns.set_palette("husl")

    def load_data(self) -> tuple:
        """載入資料"""
        # 載入車輛資料
        query_vehicles = """
            SELECT * FROM vehicle_prices
            ORDER BY scrape_datetime DESC
        """
        df_vehicles = pd.read_sql_query(query_vehicles, self.conn)

        # 載入價格趨勢
        query_trends = """
            SELECT * FROM price_trends
            ORDER BY date_recorded DESC
        """
        df_trends = pd.read_sql_query(query_trends, self.conn)

        # 轉換日期格式
        if not df_vehicles.empty:
            df_vehicles['scrape_datetime'] = pd.to_datetime(df_vehicles['scrape_datetime'])
        if not df_trends.empty:
            df_trends['date_recorded'] = pd.to_datetime(df_trends['date_recorded'])

        return df_vehicles, df_trends

    def plot_price_distribution(self, df_vehicles: pd.DataFrame):
        """
        繪製價格分布圖

        Args:
            df_vehicles: 車輛資料DataFrame
        """
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Tesla 認證中古車價格分布分析', fontsize=16, fontweight='bold')

        # 1. 整體價格分布直方圖
        ax1 = axes[0, 0]
        ax1.hist(df_vehicles['price'] / 10000, bins=30, edgecolor='black', alpha=0.7)
        ax1.set_xlabel('價格 (萬元 NTD)')
        ax1.set_ylabel('車輛數量')
        ax1.set_title('整體價格分布')
        ax1.grid(True, alpha=0.3)

        # 添加統計資訊
        mean_price = df_vehicles['price'].mean() / 10000
        median_price = df_vehicles['price'].median() / 10000
        ax1.axvline(mean_price, color='red', linestyle='--', label=f'平均: {mean_price:.1f}萬')
        ax1.axvline(median_price, color='green', linestyle='--', label=f'中位數: {median_price:.1f}萬')
        ax1.legend()

        # 2. 各車型價格箱型圖
        ax2 = axes[0, 1]
        models = df_vehicles['model'].unique()
        price_by_model = [df_vehicles[df_vehicles['model'] == model]['price'] / 10000 for model in models]
        box = ax2.boxplot(price_by_model, labels=models, patch_artist=True)

        # 設定箱型圖顏色
        colors = plt.cm.Set3(np.linspace(0, 1, len(models)))
        for patch, color in zip(box['boxes'], colors):
            patch.set_facecolor(color)

        ax2.set_xlabel('車型')
        ax2.set_ylabel('價格 (萬元 NTD)')
        ax2.set_title('各車型價格分布')
        ax2.grid(True, alpha=0.3)

        # 3. 價格與里程關係散點圖
        ax3 = axes[1, 0]
        if 'mileage' in df_vehicles.columns:
            for model in models:
                model_data = df_vehicles[df_vehicles['model'] == model]
                ax3.scatter(model_data['mileage'] / 1000,
                          model_data['price'] / 10000,
                          label=model, alpha=0.6, s=50)

            ax3.set_xlabel('里程數 (千公里)')
            ax3.set_ylabel('價格 (萬元 NTD)')
            ax3.set_title('價格與里程關係')
            ax3.legend()
            ax3.grid(True, alpha=0.3)

            # 添加趨勢線
            if len(df_vehicles) > 10:
                z = np.polyfit(df_vehicles['mileage'].fillna(0) / 1000,
                             df_vehicles['price'] / 10000, 1)
                p = np.poly1d(z)
                x_trend = np.linspace(0, df_vehicles['mileage'].max() / 1000, 100)
                ax3.plot(x_trend, p(x_trend), "r--", alpha=0.5, label='趨勢線')

        # 4. 各車型庫存數量圓餅圖
        ax4 = axes[1, 1]
        model_counts = df_vehicles['model'].value_counts()
        wedges, texts, autotexts = ax4.pie(model_counts.values,
                                           labels=model_counts.index,
                                           autopct='%1.1f%%',
                                           startangle=90)

        # 改善圓餅圖文字
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')

        ax4.set_title('各車型庫存比例')

        plt.tight_layout()
        plt.savefig('tesla_price_distribution.png', dpi=300, bbox_inches='tight')
        plt.show()

    def plot_price_trends(self, df_trends: pd.DataFrame):
        """
        繪製價格趨勢圖

        Args:
            df_trends: 價格趨勢DataFrame
        """
        if df_trends.empty:
            print("無價格趨勢資料")
            return

        fig, axes = plt.subplots(2, 1, figsize=(15, 10))
        fig.suptitle('Tesla 認證中古車價格趨勢分析', fontsize=16, fontweight='bold')

        # 1. 平均價格趨勢
        ax1 = axes[0]

        # 按日期和車型分組計算平均價格
        daily_avg = df_trends.groupby(['date_recorded', 'model'])['price'].mean().reset_index()

        for model in daily_avg['model'].unique():
            model_data = daily_avg[daily_avg['model'] == model]
            ax1.plot(model_data['date_recorded'],
                    model_data['price'] / 10000,
                    marker='o', label=model, linewidth=2)

        ax1.set_xlabel('日期')
        ax1.set_ylabel('平均價格 (萬元 NTD)')
        ax1.set_title('各車型平均價格趨勢')
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)

        # 格式化x軸日期
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax1.xaxis.set_major_locator(mdates.DayLocator(interval=7))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # 2. 價格變動熱力圖
        ax2 = axes[1]

        # 準備熱力圖資料
        pivot_data = df_trends.pivot_table(
            values='change_percentage',
            index='model',
            columns=df_trends['date_recorded'].dt.date,
            aggfunc='mean'
        )

        if not pivot_data.empty:
            sns.heatmap(pivot_data,
                       annot=True,
                       fmt='.1f',
                       cmap='RdYlGn_r',
                       center=0,
                       ax=ax2,
                       cbar_kws={'label': '價格變動百分比 (%)'}
                       )

            ax2.set_title('價格變動熱力圖')
            ax2.set_xlabel('日期')
            ax2.set_ylabel('車型')
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        plt.tight_layout()
        plt.savefig('tesla_price_trends.png', dpi=300, bbox_inches='tight')
        plt.show()

    def plot_market_insights(self, df_vehicles: pd.DataFrame):
        """
        繪製市場洞察圖表

        Args:
            df_vehicles: 車輛資料DataFrame
        """
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Tesla 認證中古車市場洞察', fontsize=16, fontweight='bold')

        # 1. 新車輛上架趨勢
        ax1 = axes[0, 0]

        # 計算每天新增車輛數
        df_vehicles['date'] = df_vehicles['scrape_datetime'].dt.date
        daily_new = df_vehicles.groupby('date').size().reset_index(name='count')

        ax1.plot(daily_new['date'], daily_new['count'],
                marker='o', linewidth=2, color='steelblue')
        ax1.fill_between(daily_new['date'], daily_new['count'],
                        alpha=0.3, color='steelblue')
        ax1.set_xlabel('日期')
        ax1.set_ylabel('新增車輛數')
        ax1.set_title('每日新增車輛趨勢')
        ax1.grid(True, alpha=0.3)
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # 2. 價格區間分布
        ax2 = axes[0, 1]

        price_ranges = [
            (0, 150, '150萬以下'),
            (150, 200, '150-200萬'),
            (200, 250, '200-250萬'),
            (250, 300, '250-300萬'),
            (300, float('inf'), '300萬以上')
        ]

        range_counts = []
        range_labels = []

        for low, high, label in price_ranges:
            count = len(df_vehicles[(df_vehicles['price'] >= low*10000) &
                                   (df_vehicles['price'] < high*10000)])
            range_counts.append(count)
            range_labels.append(label)

        bars = ax2.bar(range_labels, range_counts, color='coral')
        ax2.set_xlabel('價格區間')
        ax2.set_ylabel('車輛數量')
        ax2.set_title('價格區間分布')

        # 添加數值標籤
        for bar, count in zip(bars, range_counts):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{count}',
                    ha='center', va='bottom')

        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        # 3. 顏色偏好分析
        ax3 = axes[1, 0]

        if 'exterior_color' in df_vehicles.columns:
            color_counts = df_vehicles['exterior_color'].value_counts().head(8)

            colors_map = {
                'Pearl White': '#F8F8FF',
                'Solid Black': '#000000',
                'Midnight Silver': '#696969',
                'Deep Blue': '#00008B',
                'Red': '#DC143C',
                'Gray': '#808080',
                'Blue': '#4169E1',
                'White': '#FFFFFF'
            }

            bar_colors = [colors_map.get(c, '#CCCCCC') for c in color_counts.index]

            bars = ax3.barh(range(len(color_counts)), color_counts.values)

            for bar, color in zip(bars, bar_colors):
                bar.set_color(color)
                bar.set_edgecolor('black')

            ax3.set_yticks(range(len(color_counts)))
            ax3.set_yticklabels(color_counts.index)
            ax3.set_xlabel('數量')
            ax3.set_title('外觀顏色偏好')
            ax3.invert_yaxis()

        # 4. 年份分布
        ax4 = axes[1, 1]

        if 'year' in df_vehicles.columns:
            year_counts = df_vehicles['year'].value_counts().sort_index()

            ax4.bar(year_counts.index, year_counts.values,
                   color='teal', edgecolor='black')
            ax4.set_xlabel('年份')
            ax4.set_ylabel('車輛數量')
            ax4.set_title('車輛年份分布')
            ax4.grid(True, alpha=0.3, axis='y')

            # 添加數值標籤
            for x, y in zip(year_counts.index, year_counts.values):
                ax4.text(x, y, str(y), ha='center', va='bottom')

        plt.tight_layout()
        plt.savefig('tesla_market_insights.png', dpi=300, bbox_inches='tight')
        plt.show()

    def generate_summary_report(self, df_vehicles: pd.DataFrame, df_trends: pd.DataFrame):
        """
        生成摘要報告

        Args:
            df_vehicles: 車輛資料DataFrame
            df_trends: 價格趨勢DataFrame
        """
        print("\n" + "="*80)
        print("Tesla 認證中古車市場分析報告摘要")
        print("="*80)
        print(f"報告生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*80)

        # 基本統計
        print("\n【基本統計資訊】")
        print(f"總記錄數: {len(df_vehicles):,} 筆")
        print(f"唯一車輛數: {df_vehicles['vin'].nunique():,} 輛")
        print(f"資料時間範圍: {df_vehicles['scrape_datetime'].min()} 至 {df_vehicles['scrape_datetime'].max()}")

        # 價格統計
        print("\n【價格統計】")
        print(f"平均價格: NT${df_vehicles['price'].mean():,.0f}")
        print(f"中位數價格: NT${df_vehicles['price'].median():,.0f}")
        print(f"最低價格: NT${df_vehicles['price'].min():,.0f}")
        print(f"最高價格: NT${df_vehicles['price'].max():,.0f}")
        print(f"價格標準差: NT${df_vehicles['price'].std():,.0f}")

        # 各車型統計
        print("\n【各車型詳細統計】")
        for model in df_vehicles['model'].unique():
            model_data = df_vehicles[df_vehicles['model'] == model]
            print(f"\n{model}:")
            print(f"  數量: {len(model_data)} 筆記錄")
            print(f"  平均價格: NT${model_data['price'].mean():,.0f}")
            print(f"  價格範圍: NT${model_data['price'].min():,.0f} - NT${model_data['price'].max():,.0f}")

            if 'mileage' in model_data.columns:
                print(f"  平均里程: {model_data['mileage'].mean():,.0f} km")

        # 價格趨勢分析
        if not df_trends.empty:
            print("\n【價格趨勢分析】")
            recent_trends = df_trends[df_trends['date_recorded'] >=
                                     df_trends['date_recorded'].max() - timedelta(days=30)]

            if not recent_trends.empty:
                avg_change = recent_trends['change_percentage'].mean()
                print(f"近30天平均價格變動: {avg_change:+.2f}%")

                rising = recent_trends[recent_trends['change_percentage'] > 0]
                falling = recent_trends[recent_trends['change_percentage'] < 0]

                print(f"漲價車輛數: {len(rising)} ({len(rising)/len(recent_trends)*100:.1f}%)")
                print(f"降價車輛數: {len(falling)} ({len(falling)/len(recent_trends)*100:.1f}%)")
                print(f"價格不變: {len(recent_trends) - len(rising) - len(falling)}")

        print("\n" + "="*80)

    def run_analysis(self):
        """執行完整分析"""
        print("載入資料...")
        df_vehicles, df_trends = self.load_data()

        if df_vehicles.empty:
            print("無車輛資料可供分析")
            return

        print("生成分析圖表...")

        # 生成各種圖表
        self.plot_price_distribution(df_vehicles)
        self.plot_price_trends(df_trends)
        self.plot_market_insights(df_vehicles)

        # 生成摘要報告
        self.generate_summary_report(df_vehicles, df_trends)

        print("\n分析完成！圖表已儲存。")

    def __del__(self):
        """關閉資料庫連線"""
        if hasattr(self, 'conn'):
            self.conn.close()

def main():
    """主程式"""
    visualizer = TeslaPriceVisualizer()
    visualizer.run_analysis()

if __name__ == "__main__":
    main()

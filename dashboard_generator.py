# -*- coding: utf-8 -*-
"""
dashboard_generator.py — تولید داشبورد HTML حرفه‌ای
"""

import json
from datetime import datetime, timezone
import pandas as pd
from market_params import get_all_markets

class DashboardGenerator:
    """تولید داشبورد HTML interactive"""
    
    def __init__(self):
        self.markets = get_all_markets()
        
    def generate_html(self, signals_df: pd.DataFrame, output_path: str = "dashboard_live.html") -> None:
        """تولید فایل HTML داشبورد"""
        
        market_summary = self._prepare_market_summary(signals_df)
        
        html_content = f"""
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>سیستم تحلیل SMC/RTM/Liquidity</title>
    <style>
        * {{
            margin: 0; padding: 0; box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            color: #e0e0e0; min-height: 100vh; padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        header {{
            text-align: center; margin-bottom: 30px; border-bottom: 2px solid #00d4ff; padding-bottom: 20px;
        }}
        h1 {{
            font-size: 2.5em; color: #00d4ff; text-shadow: 0 0 10px rgba(0, 212, 255, 0.5); margin-bottom: 10px;
        }}
        .timestamp {{ color: #888; font-size: 0.9em; }}
        .grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px;
        }}
        .card {{
            background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(0, 212, 255, 0.3); border-radius: 10px; padding: 20px;
            backdrop-filter: blur(10px); box-shadow: 0 8px 32px rgba(0, 212, 255, 0.1); transition: all 0.3s ease;
        }}
        .card:hover {{ border-color: #00d4ff; box-shadow: 0 8px 32px rgba(0, 212, 255, 0.3); }}
        .card-title {{
            color: #00d4ff; font-size: 1.2em; margin-bottom: 15px; border-bottom: 1px solid rgba(0, 212, 255, 0.2); padding-bottom: 10px;
        }}
        .stat {{
            display: flex; justify-content: space-between; align-items: center; margin: 10px 0; padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .stat-label {{ color: #aaa; }}
        .stat-value {{ color: #00d4ff; font-weight: bold; font-size: 1.1em; }}
        .table-container {{
            overflow-x: auto; background: rgba(255, 255, 255, 0.05); border-radius: 10px; padding: 20px; margin-bottom: 30px;
        }}
        table {{
            width: 100%; border-collapse: collapse; color: #e0e0e0;
        }}
        th {{
            background: rgba(0, 212, 255, 0.2); color: #00d4ff; padding: 12px; text-align: right; border-bottom: 2px solid #00d4ff;
        }}
        td {{
            padding: 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); text-align: right;
        }}
        tr:hover {{ background: rgba(0, 212, 255, 0.05); }}
        .badge {{
            display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 0.9em; font-weight: bold;
        }}
        .badge-long {{ background: #00ff41; color: #000; }}
        .badge-short {{ background: #ff0055; color: #fff; }}
        .footer {{ text-align: center; color: #666; margin-top: 50px; padding-top: 20px; border-top: 1px solid rgba(255, 255, 255, 0.1); }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔍 سیستم تحلیل SMC/RTM/Liquidity</h1>
            <p class="timestamp">به‌روزرسانی: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </header>
        
        <div class="grid">
"""
        
        for market in market_summary:
            html_content += f"""
            <div class="card">
                <div class="card-title">{market['display_name']}</div>
                <div class="stat">
                    <span class="stat-label">کل سیگنال‌ها:</span>
                    <span class="stat-value">{market['total_signals']}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">سیگنال‌های LONG:</span>
                    <span class="stat-value" style="color: #00ff41;">{market['long_signals']}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">سیگنال‌های SHORT:</span>
                    <span class="stat-value" style="color: #ff0055;">{market['short_signals']}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">اطمینان میانگین:</span>
                    <span class="stat-value">{market['avg_confidence']:.1%}</span>
                </div>
            </div>
"""
        
        html_content += """</div>
        
        <div class="table-container">
            <h2 style="color: #00d4ff; margin-bottom: 15px;">سیگنال‌های تولید شده</h2>
            <table>
                <thead>
                    <tr>
                        <th>تاریخ/ساعت</th>
                        <th>بازار</th>
                        <th>جهت</th>
                        <th>قیمت ورود</th>
                        <th>Stop Loss</th>
                        <th>Take Profit</th>
                        <th>اطمینان</th>
                        <th>رژیم</th>
                    </tr>
                </thead>
                <tbody>
"""
        
        if not signals_df.empty:
            for _, row in signals_df.iterrows():
                direction_class = 'long' if row['direction'] == 'LONG' else 'short'
                badge_class = 'badge-long' if row['direction'] == 'LONG' else 'badge-short'
                
                html_content += f"""
                <tr>
                    <td>{row['timestamp']}</td>
                    <td>{row['market']}</td>
                    <td><span class="badge {badge_class}">{row['direction']}</span></td>
                    <td>{row['entry_price']:.2f}</td>
                    <td>{row['sl_price']:.2f}</td>
                    <td>{row['tp_price']:.2f}</td>
                    <td>{row['sweep_confidence']:.1%}</td>
                    <td>{row['regime']}</td>
                </tr>
"""
        else:
            html_content += """
                <tr>
                    <td colspan="8" style="text-align: center; color: #888;">هیچ سیگنالی موجود نیست</td>
                </tr>
"""
        
        html_content += """
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>© 2026 سیستم تحلیل هوشمند | تمام حقوق محفوظ است</p>
        </div>
    </div>
    <script>
        setTimeout(() => { location.reload(); }, 5 * 60 * 1000);
    </script>
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ داشبورد ذخیره شد: {output_path}")
    
    def _prepare_market_summary(self, signals_df: pd.DataFrame) -> list:
        """تهیه خلاصه بازارها"""
        summary = []
        
        for market in self.markets:
            market_data = signals_df[signals_df['market'] == market['name']] if not signals_df.empty else pd.DataFrame()
            
            summary.append({
                'display_name': market['display_name'],
                'total_signals': len(market_data),
                'long_signals': len(market_data[market_data['direction'] == 'LONG']),
                'short_signals': len(market_data[market_data['direction'] == 'SHORT']),
                'avg_confidence': market_data['sweep_confidence'].mean() if not market_data.empty else 0,
            })
        
        return summary

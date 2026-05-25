import pandas as pd, json, os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
df = pd.read_csv(os.path.join(project_root, 'data', 'XAU_USD-15.csv'))
df = df.tail(100)
data = {
    'labels': df['timestamp'].astype(str).tolist(),
    'prices': df['close'].round(2).tolist(),
    'htf_bias': 'صعودی',
    'liquidity_state': 'جاروب مهندسی‌شده',
    'volatility_regime': 'انبساط',
    'smt_divergence': 'فعال',
    'inventory_pressure': 'برنامه فروش',
    'liquidity_probability': 78,
    'session': 'لندن / نیویورک',
    'narrative': 'بازار در ناحیه Premium با رفتار فریب مهندسی‌شده.',
    'logs': [
        {'type':'buy','text':'[۰۹:۳۱] جاروب نقدینگی بالای سقف'},
        {'type':'','text':'[۰۹:۳۲] عدم تعادل موجودی'},
        {'type':'sell','text':'[۰۹:۳۳] برنامه فروش تهاجمی'},
        {'type':'','text':'[۰۹:۳۴] رژیم انبساط نوسان'}
    ]
}
with open(os.path.join(project_root, 'dashboard_data.js'), 'w', encoding='utf-8') as f:
    f.write('window.MARKET_DATA = ' + json.dumps(data, ensure_ascii=False, indent=2) + ';')
print('✅ dashboard_data.js آماده شد.')
"""
智投分析 - 股票分析后端服务
多数据源备份：东方财富、腾讯财经、新浪财经
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
import json
import time
import random
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ==================== 通用请求头 ====================

HEADERS_EASTMONEY = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://quote.eastmoney.com/'
}

HEADERS_SINA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://finance.sina.com.cn'
}

HEADERS_TENCENT = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://gu.qq.com/'
}

# ==================== 新浪财经API ====================

def get_sina_quote(code):
    """新浪财经实时行情"""
    if code.startswith('6'):
        symbol = f'sh{code}'
    else:
        symbol = f'sz{code}'
    
    url = f'https://hq.sinajs.cn/list={symbol}'
    
    try:
        resp = requests.get(url, headers=HEADERS_SINA, timeout=8)
        resp.encoding = 'gbk'
        text = resp.text
        
        # 解析格式: var hq_str_sh600519="贵州茅台,1680.00,1675.00,...";
        start = text.find('"')
        end = text.rfind('"')
        if start < 0 or end <= start:
            return None
        
        data_str = text[start+1:end]
        fields = data_str.split(',')
        if len(fields) < 32:
            return None
        
        price = float(fields[3])
        pre_close = float(fields[2])
        change_pct = ((price - pre_close) / pre_close * 100) if pre_close > 0 else 0
        change_amt = price - pre_close
        
        return {
            'code': code,
            'name': fields[0],
            'price': price,
            'change': round(change_pct, 2),
            'changeAmount': round(change_amt, 2),
            'open': float(fields[1]),
            'high': float(fields[4]),
            'low': float(fields[5]),
            'preClose': pre_close,
            'volume': float(fields[8]),
            'amount': float(fields[9]),
            'turnover': float(fields[38]) if len(fields) > 38 and fields[38] else 0,
            'amplitude': 0,
            'pe': float(fields[39]) if len(fields) > 39 and fields[39] else 0,
            'pb': 0,
            'totalMarketCap': float(fields[45]) * 10000 / 100000000 if len(fields) > 45 and fields[45] else 0,
            'floatMarketCap': float(fields[44]) * 10000 / 100000000 if len(fields) > 44 and fields[44] else 0,
            'volumeRatio': 0,
        }
    except Exception as e:
        print(f'新浪行情失败({code}): {e}')
        return None


# ==================== 腾讯财经API ====================

def get_tencent_quote(code):
    """腾讯财经实时行情"""
    if code.startswith('6'):
        symbol = f'sh{code}'
    else:
        symbol = f'sz{code}'
    
    url = f'https://qt.gtimg.cn/q={symbol}'
    
    try:
        resp = requests.get(url, headers=HEADERS_TENCENT, timeout=8)
        resp.encoding = 'gbk'
        text = resp.text
        
        # 解析格式: v_sh600519="1~贵州茅台~600519~..."
        start = text.find('"')
        end = text.rfind('"')
        if start < 0 or end <= start:
            return None
        
        data_str = text[start+1:end]
        fields = data_str.split('~')
        if len(fields) < 45:
            return None
        
        price = float(fields[3])
        pre_close = float(fields[4])
        change_pct = float(fields[32]) if fields[32] else 0
        change_amt = float(fields[31]) if fields[31] else 0
        
        return {
            'code': code,
            'name': fields[1],
            'price': price,
            'change': round(change_pct, 2),
            'changeAmount': round(change_amt, 2),
            'open': float(fields[5]) if fields[5] else 0,
            'high': float(fields[33]) if fields[33] else 0,
            'low': float(fields[34]) if fields[34] else 0,
            'preClose': pre_close,
            'volume': float(fields[6]) if fields[6] else 0,
            'amount': float(fields[37]) if fields[37] else 0,
            'turnover': float(fields[38]) if len(fields) > 38 and fields[38] else 0,
            'amplitude': float(fields[43]) if len(fields) > 43 and fields[43] else 0,
            'pe': float(fields[39]) if len(fields) > 39 and fields[39] else 0,
            'pb': float(fields[46]) if len(fields) > 46 and fields[46] else 0,
            'totalMarketCap': float(fields[45]) / 10000 if len(fields) > 45 and fields[45] else 0,
            'floatMarketCap': float(fields[44]) / 10000 if len(fields) > 44 and fields[44] else 0,
            'volumeRatio': float(fields[49]) if len(fields) > 49 and fields[49] else 0,
        }
    except Exception as e:
        print(f'腾讯行情失败({code}): {e}')
        return None


# ==================== 东方财富API ====================

def get_eastmoney_quote(code):
    """东方财富实时行情"""
    for attempt in range(2):
        try:
            if code.startswith('6'):
                secid = f'1.{code}'
            else:
                secid = f'0.{code}'
            
            url = f'https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f57,f58,f60,f107,f116,f117,f162,f167,f168,f169,f170,f171,f177,f183,f184'
            
            resp = requests.get(url, headers=HEADERS_EASTMONEY, timeout=8)
            data = resp.json()
            if data.get('data'):
                d = data['data']
                return {
                    'code': d.get('f57', code),
                    'name': d.get('f58', ''),
                    'price': d.get('f43', 0) / 100 if d.get('f43') else 0,
                    'change': d.get('f170', 0) / 100 if d.get('f170') else 0,
                    'changeAmount': d.get('f169', 0) / 100 if d.get('f169') else 0,
                    'open': d.get('f46', 0) / 100 if d.get('f46') else 0,
                    'high': d.get('f44', 0) / 100 if d.get('f44') else 0,
                    'low': d.get('f45', 0) / 100 if d.get('f45') else 0,
                    'preClose': d.get('f60', 0) / 100 if d.get('f60') else 0,
                    'volume': d.get('f47', 0),
                    'amount': d.get('f48', 0),
                    'turnover': d.get('f168', 0) / 100 if d.get('f168') else 0,
                    'amplitude': d.get('f171', 0) / 100 if d.get('f171') else 0,
                    'pe': d.get('f162', 0) / 100 if d.get('f162') else 0,
                    'pb': d.get('f167', 0) / 100 if d.get('f167') else 0,
                    'totalMarketCap': d.get('f116', 0) / 100000000 if d.get('f116') else 0,
                    'floatMarketCap': d.get('f117', 0) / 100000000 if d.get('f117') else 0,
                    'volumeRatio': d.get('f50', 0) / 100 if d.get('f50') else 0,
                }
        except Exception as e:
            if attempt < 1:
                time.sleep(0.3)
                continue
            print(f'东方财富行情失败({code}): {e}')
    return None


def get_stock_quote(code):
    """获取股票实时行情（多数据源备份）"""
    # 按顺序尝试：新浪 → 腾讯 → 东方财富
    # 新浪和腾讯的服务器在国内，海外访问也比较稳定
    
    quote = get_sina_quote(code)
    if quote and quote['price'] > 0:
        return quote
    
    quote = get_tencent_quote(code)
    if quote and quote['price'] > 0:
        return quote
    
    quote = get_eastmoney_quote(code)
    if quote and quote['price'] > 0:
        return quote
    
    return None


def get_kline_data(code, klt=101, fqt=1, lmt=60):
    """获取K线数据
    klt: 101=日K, 102=周K, 103=月K, 5=5分钟, 15=15分钟, 30=30分钟, 60=60分钟
    fqt: 0=不复权, 1=前复权, 2=后复权
    lmt: 返回数量
    """
    # 腾讯财经K线API（更稳定）
    if code.startswith('6'):
        symbol = f'sh{code}'
    else:
        symbol = f'sz{code}'
    
    period_map = {101: 'day', 102: 'week', 103: 'month'}
    period = period_map.get(klt, 'day')
    
    fqt_map = {0: '', 1: 'qfq', 2: 'hfq'}
    fqt_str = fqt_map.get(fqt, 'qfq')
    
    url = f'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},{period},,,{lmt},{fqt_str}'
    
    try:
        resp = requests.get(url, headers=HEADERS_TENCENT, timeout=10)
        data = resp.json()
        
        # 解析腾讯财经返回格式
        klines = []
        if data.get('data'):
            stock_data = data['data'].get(symbol, {})
            # 前复权数据在 qfqday 字段，不复权在 day 字段
            kline_key = f'{fqt_str}{period}' if fqt_str else period
            kline_data = stock_data.get(kline_key, stock_data.get(period, []))
            
            for line in kline_data:
                amount = 0
                if len(line) > 6 and isinstance(line[6], (int, float, str)):
                    try:
                        amount = float(line[6])
                    except:
                        amount = 0
                klines.append({
                    'date': str(line[0]),
                    'open': float(line[1]),
                    'close': float(line[2]),
                    'high': float(line[3]),
                    'low': float(line[4]),
                    'volume': int(float(line[5])),
                    'amount': amount
                })
            return klines
        else:
            print(f'K线(腾讯)返回无data: code={code}')
    except Exception as e:
        print(f'获取K线失败(腾讯): {e}')
    
    # 降级：使用东方财富API
    if code.startswith('6'):
        secid = f'1.{code}'
    else:
        secid = f'0.{code}'
    
    url = f'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57&klt={klt}&fqt={fqt}&lmt={lmt}'
    
    try:
        resp = requests.get(url, headers=HEADERS_EASTMONEY, timeout=10)
        data = resp.json()
        if data.get('data') and data['data'].get('klines'):
            klines = []
            for line in data['data']['klines']:
                parts = line.split(',')
                klines.append({
                    'date': parts[0],
                    'open': float(parts[1]),
                    'close': float(parts[2]),
                    'high': float(parts[3]),
                    'low': float(parts[4]),
                    'volume': int(float(parts[5])),
                    'amount': float(parts[6])
                })
            return klines
    except Exception as e:
        print(f'获取K线失败(东方财富): {e}')
    
    return []


def search_stocks(keyword):
    """搜索股票"""
    url = f'https://searchapi.eastmoney.com/api/suggest/get?input={keyword}&type=14&token=D43BF722C8E33BDC906FB84D85E326E8&count=10'
    
    try:
        resp = requests.get(url, headers=HEADERS_EASTMONEY, timeout=10)
        data = resp.json()
        results = []
        if data.get('QuotationCodeTable') and data['QuotationCodeTable'].get('Data'):
            for item in data['QuotationCodeTable']['Data']:
                results.append({
                    'code': item.get('Code', ''),
                    'name': item.get('Name', ''),
                    'market': item.get('MarketType', ''),
                    'mktNum': item.get('MktNum', '')
                })
        return results
    except Exception as e:
        print(f'搜索股票失败: {e}')
    return []


def get_sector_list():
    """获取行业板块列表及涨幅"""
    url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:2&fields=f2,f3,f4,f12,f14'
    
    try:
        resp = requests.get(url, headers=HEADERS_EASTMONEY, timeout=10)
        data = resp.json()
        sectors = []
        if data.get('data') and data['data'].get('diff'):
            for item in data['data']['diff']:
                sectors.append({
                    'code': item.get('f12', ''),
                    'name': item.get('f14', ''),
                    'change': item.get('f3', 0),  # 涨跌幅
                    'changeAmount': item.get('f4', 0),  # 涨跌点
                    'price': item.get('f2', 0) / 100 if item.get('f2') else 0,
                })
        return sectors
    except Exception as e:
        print(f'获取板块失败: {e}')
    return []


def get_index_list():
    """获取主要指数"""
    indices = [
        {'code': '000001', 'name': '上证指数', 'secid': '1.000001'},
        {'code': '399001', 'name': '深证成指', 'secid': '0.399001'},
        {'code': '399006', 'name': '创业板指', 'secid': '0.399006'},
    ]
    
    result = []
    for idx in indices:
        url = f'https://push2.eastmoney.com/api/qt/stock/get?secid={idx["secid"]}&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f169,f170'
        try:
            resp = requests.get(url, headers=HEADERS_EASTMONEY, timeout=5)
            data = resp.json()
            if data.get('data'):
                d = data['data']
                result.append({
                    'code': idx['code'],
                    'name': idx['name'],
                    'price': d.get('f43', 0) / 100 if d.get('f43') else 0,
                    'change': d.get('f170', 0) / 100 if d.get('f170') else 0,
                    'changeAmount': d.get('f169', 0) / 100 if d.get('f169') else 0,
                })
        except Exception as e:
            print(f'获取指数{idx["name"]}失败: {e}')
            result.append({
                'code': idx['code'],
                'name': idx['name'],
                'price': 0,
                'change': 0,
                'changeAmount': 0
            })
    return result


def get_sector_stocks(sector_code, limit=10):
    """获取板块成分股"""
    url = f'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz={limit}&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:{sector_code}+f:!50&fields=f2,f3,f4,f5,f6,f7,f12,f14'
    
    try:
        resp = requests.get(url, headers=HEADERS_EASTMONEY, timeout=10)
        data = resp.json()
        stocks = []
        if data.get('data') and data['data'].get('diff'):
            for item in data['data']['diff']:
                stocks.append({
                    'code': item.get('f12', ''),
                    'name': item.get('f14', ''),
                    'price': item.get('f2', 0) / 100 if item.get('f2') else 0,
                    'change': item.get('f3', 0),
                    'changeAmount': item.get('f4', 0) / 100 if item.get('f4') else 0,
                    'volume': item.get('f5', 0),
                    'amount': item.get('f6', 0),
                    'amplitude': item.get('f7', 0),
                })
        return stocks
    except Exception as e:
        print(f'获取板块成分股失败: {e}')
    return []


def get_financial_data(code):
    """获取主要财务指标"""
    # 东方财富财务指标接口
    if code.startswith('6'):
        secid = f'SH{code}'
    else:
        secid = f'SZ{code}'
    
    url = f'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_LICO_FN_CPD&columns=ALL&filter=(SECURITY_CODE="{code}")&pageSize=4&sortColumns=REPORT_DATE&sortTypes=-1'
    
    try:
        resp = requests.get(url, headers=HEADERS_EASTMONEY, timeout=10)
        data = resp.json()
        records = []
        if data.get('result') and data['result'].get('data'):
            for item in data['result']['data'][:4]:
                records.append({
                    'reportDate': item.get('REPORT_DATE', '')[:10],
                    'totalRevenue': item.get('TOTAL_OPERATE_INCOME', 0),  # 营业总收入
                    'netProfit': item.get('PARENT_NETPROFIT', 0),  # 归母净利润
                    'revenueYoy': item.get('TOTAL_OPERATE_INCOME_YOY', 0),  # 营收同比
                    'profitYoy': item.get('PARENT_NETPROFIT_YOY', 0),  # 净利同比
                    'eps': item.get('BASIC_EPS', 0),  # 基本每股收益
                    'roe': item.get('WEIGHTAVG_ROE', 0),  # 净资产收益率
                    'grossMargin': item.get('GROSS_PROFIT_RATIO', 0),  # 毛利率
                    'netMargin': item.get('DEDUCT_PARENT_NETPROFIT_RATIO', 0),  # 净利率
                })
        return records
    except Exception as e:
        print(f'获取财务数据失败: {e}')
    return []


# ==================== 技术分析计算 ====================

def calculate_ma(prices, period):
    """计算简单移动平均线"""
    if len(prices) < period:
        return []
    mas = []
    for i in range(period - 1, len(prices)):
        ma = sum(prices[i-period+1:i+1]) / period
        mas.append(round(ma, 2))
    return mas


def calculate_macd(closes, fast=12, slow=26, signal=9):
    """计算MACD"""
    # EMA计算
    def ema(data, period):
        result = []
        multiplier = 2 / (period + 1)
        for i, val in enumerate(data):
            if i == 0:
                result.append(val)
            else:
                result.append(val * multiplier + result[-1] * (1 - multiplier))
        return result
    
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    
    # DIF = EMA12 - EMA26
    dif = [round(ema_fast[i] - ema_slow[i], 4) for i in range(len(closes))]
    
    # DEA = DIF的9日EMA
    dea = ema(dif, signal)
    
    # MACD柱 = 2 * (DIF - DEA)
    macd_bar = [round(2 * (dif[i] - dea[i]), 4) for i in range(len(closes))]
    
    return {
        'dif': dif[-1],
        'dea': dea[-1],
        'macd': macd_bar[-1],
        'isGoldenCross': len(dif) >= 2 and dif[-1] > dea[-1] and dif[-2] <= dea[-2],
        'isDeathCross': len(dif) >= 2 and dif[-1] < dea[-1] and dif[-2] >= dea[-2],
        'isBullish': dif[-1] > dea[-1]
    }


def calculate_kdj(highs, lows, closes, n=9, m1=3, m2=3):
    """计算KDJ"""
    rsv_list = []
    for i in range(len(closes)):
        if i < n - 1:
            rsv_list.append(50)
            continue
        high_n = max(highs[i-n+1:i+1])
        low_n = min(lows[i-n+1:i+1])
        if high_n == low_n:
            rsv = 50
        else:
            rsv = (closes[i] - low_n) / (high_n - low_n) * 100
        rsv_list.append(rsv)
    
    k_values = [50]
    d_values = [50]
    for rsv in rsv_list[1:]:
        k = (m1 - 1) / m1 * k_values[-1] + 1 / m1 * rsv
        d = (m2 - 1) / m2 * d_values[-1] + 1 / m2 * k
        k_values.append(k)
        d_values.append(d)
    
    j_values = [3 * k_values[i] - 2 * d_values[i] for i in range(len(k_values))]
    
    k = round(k_values[-1], 2)
    d = round(d_values[-1], 2)
    j = round(j_values[-1], 2)
    
    return {
        'k': k,
        'd': d,
        'j': j,
        'isOverbought': k > 80,
        'isOversold': k < 20,
        'signal': '超买' if k > 80 else '超卖' if k < 20 else '中性'
    }


def calculate_rsi(closes, period=14):
    """计算RSI"""
    if len(closes) < period + 1:
        return 50
    
    gains = []
    losses = []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    
    # 计算初始平均涨跌
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # 平滑计算
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def calculate_boll(closes, period=20, k=2):
    """计算布林带"""
    if len(closes) < period:
        return {'upper': 0, 'middle': 0, 'lower': 0, 'position': '中轨'}
    
    # 中轨 = MA20
    middle = sum(closes[-period:]) / period
    
    # 计算标准差
    variance = sum((x - middle) ** 2 for x in closes[-period:]) / period
    std = variance ** 0.5
    
    upper = middle + k * std
    lower = middle - k * std
    
    current = closes[-1]
    if current >= upper:
        position = '上轨上方'
    elif current >= middle:
        position = '上轨与中轨之间'
    elif current >= lower:
        position = '中轨与下轨之间'
    else:
        position = '下轨下方'
    
    return {
        'upper': round(upper, 2),
        'middle': round(middle, 2),
        'lower': round(lower, 2),
        'position': position,
        'isBullish': current >= middle
    }


def calculate_support_resistance(klines):
    """计算支撑压力位"""
    if not klines:
        return {'support1': 0, 'support2': 0, 'resistance1': 0, 'resistance2': 0}
    
    closes = [k['close'] for k in klines]
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    current = closes[-1]
    
    # 找近期低点作为支撑
    recent_lows = sorted(lows[-30:])[:5]
    support1 = round(sum(recent_lows) / len(recent_lows), 2)  # 强支撑
    support2 = round(current * 0.97, 2)  # 弱支撑
    
    # 找近期高点作为压力
    recent_highs = sorted(highs[-30:], reverse=True)[:5]
    resistance1 = round(sum(recent_highs) / len(recent_highs), 2)  # 弱压力
    resistance2 = round(current * 1.08, 2)  # 强压力
    
    # 确保价格排序正确
    if support1 > support2:
        support1, support2 = support2, support1
    if resistance1 > resistance2:
        resistance1, resistance2 = resistance2, resistance1
    
    return {
        'support1': support1,  # 强支撑
        'support2': support2,  # 弱支撑
        'resistance1': resistance1,  # 弱压力
        'resistance2': resistance2  # 强压力
    }


def generate_analysis(quote, klines):
    """生成综合分析和买卖建议"""
    if not quote or not klines or len(klines) < 20:
        return None
    
    closes = [k['close'] for k in klines]
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    current_price = quote['price']
    
    # 计算各指标
    macd = calculate_macd(closes)
    kdj = calculate_kdj(highs, lows, closes)
    rsi = calculate_rsi(closes)
    boll = calculate_boll(closes)
    sr = calculate_support_resistance(klines)
    
    # 均线系统
    ma5 = calculate_ma(closes, 5)
    ma10 = calculate_ma(closes, 10)
    ma20 = calculate_ma(closes, 20)
    ma60 = calculate_ma(closes, 60) if len(closes) >= 60 else ma20
    
    ma5_val = ma5[-1] if ma5 else current_price
    ma10_val = ma10[-1] if ma10 else current_price
    ma20_val = ma20[-1] if ma20 else current_price
    
    # 判断均线排列
    if ma5_val > ma10_val > ma20_val:
        ma_trend = '多头排列'
        ma_score = 8
    elif ma5_val < ma10_val < ma20_val:
        ma_trend = '空头排列'
        ma_score = 2
    else:
        ma_trend = '缠绕震荡'
        ma_score = 5
    
    # 技术面评分 (0-10分)
    tech_score = 5
    
    # MACD贡献
    if macd['isBullish']:
        tech_score += 1
    if macd['isGoldenCross']:
        tech_score += 0.5
    if macd['isDeathCross']:
        tech_score -= 0.5
    
    # KDJ贡献
    if kdj['k'] < 20:
        tech_score += 1  # 超卖可能反弹
    elif kdj['k'] > 80:
        tech_score -= 1  # 超买可能回调
    
    # RSI贡献
    if rsi < 30:
        tech_score += 0.5
    elif rsi > 70:
        tech_score -= 0.5
    
    # 均线贡献
    tech_score += (ma_score - 5) * 0.3
    
    # 布林带
    if boll['isBullish']:
        tech_score += 0.3
    
    # 限制在0-10
    tech_score = max(0, min(10, tech_score))
    
    # 基本面评分 (基于PE/PB/市值等简化评估)
    fund_score = 6
    if quote.get('pe') and quote['pe'] > 0:
        if quote['pe'] < 15:
            fund_score += 2
        elif quote['pe'] < 25:
            fund_score += 1
        elif quote['pe'] > 50:
            fund_score -= 1
    
    if quote.get('pb'):
        if quote['pb'] < 2:
            fund_score += 0.5
        elif quote['pb'] > 10:
            fund_score -= 0.5
    
    fund_score = max(0, min(10, fund_score))
    
    # 估值评分
    val_score = 5
    if quote.get('pe') and quote['pe'] > 0:
        if quote['pe'] < 20:
            val_score = 8
        elif quote['pe'] < 30:
            val_score = 7
        elif quote['pe'] < 40:
            val_score = 5
        elif quote['pe'] < 60:
            val_score = 3
        else:
            val_score = 2
    
    # 行业地位评分 (基于市值简化)
    ind_score = 5
    if quote.get('totalMarketCap'):
        if quote['totalMarketCap'] > 5000:
            ind_score = 9
        elif quote['totalMarketCap'] > 2000:
            ind_score = 8
        elif quote['totalMarketCap'] > 1000:
            ind_score = 7
        elif quote['totalMarketCap'] > 500:
            ind_score = 6
        elif quote['totalMarketCap'] < 100:
            ind_score = 4
    
    # 综合评分
    total_score = tech_score * 0.3 + fund_score * 0.3 + val_score * 0.2 + ind_score * 0.2
    
    # 评级
    if total_score >= 7.5:
        rating = '买入'
        rating_class = 'buy'
    elif total_score >= 6:
        rating = '持有'
        rating_class = 'hold'
    else:
        rating = '观望'
        rating_class = 'sell'
    
    # 买卖价位
    buy_zone_low = round(current_price * 0.92, 2)
    buy_zone_high = round(current_price * 0.97, 2)
    sell_zone_low = round(current_price * 1.10, 2)
    sell_zone_high = round(current_price * 1.20, 2)
    
    # 根据支撑压力位调整
    if sr['support1'] > 0:
        buy_zone_low = min(buy_zone_low, sr['support1'])
        buy_zone_high = max(buy_zone_high, sr['support2'])
    
    if sr['resistance2'] > 0:
        sell_zone_high = max(sell_zone_high, sr['resistance2'])
        sell_zone_low = min(sell_zone_low, sr['resistance1'])
    
    return {
        'rating': rating,
        'ratingClass': rating_class,
        'totalScore': round(total_score, 1),
        'techScore': round(tech_score, 1),
        'fundScore': round(fund_score, 1),
        'valScore': round(val_score, 1),
        'indScore': round(ind_score, 1),
        'macd': macd,
        'kdj': kdj,
        'rsi': rsi,
        'boll': boll,
        'supportResistance': sr,
        'maTrend': ma_trend,
        'ma5': ma5_val,
        'ma10': ma10_val,
        'ma20': ma20_val,
        'buyZone': f'{buy_zone_low:.2f}-{buy_zone_high:.2f}',
        'sellZone': f'{sell_zone_low:.2f}-{sell_zone_high:.2f}',
        'buyZoneLow': buy_zone_low,
        'buyZoneHigh': buy_zone_high,
        'sellZoneLow': sell_zone_low,
        'sellZoneHigh': sell_zone_high,
        'stopLoss': round(current_price * 0.90, 2),
    }


# ==================== API接口 ====================

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/api/search')
def api_search():
    """搜索股票"""
    keyword = request.args.get('q', '').strip()
    if not keyword:
        return jsonify({'success': False, 'message': '请输入搜索关键词'})
    
    results = search_stocks(keyword)
    
    # 备用方案：如果输入是6位纯数字代码，直接尝试获取行情验证
    # 这样搜索API失败时，直接输代码也能添加
    if len(results) == 0 and keyword.isdigit() and len(keyword) == 6:
        quote = get_stock_quote(keyword)
        if quote and quote.get('name'):
            results = [{
                'code': keyword,
                'name': quote['name'],
                'market': 2 if keyword.startswith('3') or keyword.startswith('0') else 1,
                'mktNum': ''
            }]
    
    # 修复名称编码问题（东方财富搜索API返回的名称有时是乱码）
    for r in results:
        if r.get('name') and ('Ã' in r['name'] or 'é' in r['name'] or '¿' in r['name']):
            # 名称乱码，尝试用行情接口获取正确名称
            quote = get_stock_quote(r['code'])
            if quote and quote.get('name'):
                r['name'] = quote['name']
    
    return jsonify({'success': True, 'data': results})


@app.route('/api/quote')
def api_quote():
    """获取股票实时行情"""
    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'message': '请输入股票代码'})
    
    # 提取纯数字代码
    code = ''.join(filter(str.isdigit, code))
    if not code:
        return jsonify({'success': False, 'message': '股票代码格式错误'})
    
    quote = get_stock_quote(code)
    if quote:
        return jsonify({'success': True, 'data': quote})
    else:
        return jsonify({'success': False, 'message': '获取行情失败'})


@app.route('/api/quotes')
def api_quotes():
    """批量获取股票行情"""
    codes = request.args.get('codes', '').strip().split(',')
    codes = [c.strip() for c in codes if c.strip()]
    
    if not codes:
        return jsonify({'success': False, 'message': '请输入股票代码'})
    
    results = []
    for code in codes:
        code_digits = ''.join(filter(str.isdigit, code))
        if code_digits:
            quote = get_stock_quote(code_digits)
            if quote:
                results.append(quote)
    
    return jsonify({'success': True, 'data': results})


@app.route('/api/kline')
def api_kline():
    """获取K线数据"""
    code = request.args.get('code', '').strip()
    period = request.args.get('period', 'day')  # day, week, month
    count = int(request.args.get('count', 60))
    
    code = ''.join(filter(str.isdigit, code))
    if not code:
        return jsonify({'success': False, 'message': '股票代码格式错误'})
    
    klt_map = {'day': 101, 'week': 102, 'month': 103}
    klt = klt_map.get(period, 101)
    
    klines = get_kline_data(code, klt=klt, lmt=count)
    return jsonify({'success': True, 'data': klines})


@app.route('/api/indices')
def api_indices():
    """获取大盘指数"""
    indices = get_index_list()
    return jsonify({'success': True, 'data': indices})


@app.route('/api/sectors')
def api_sectors():
    """获取热门板块"""
    sectors = get_sector_list()
    
    # 补充板块描述
    descriptions = {
        '银行': '低估值高股息，防御性板块',
        '证券': '市场风向标，弹性大',
        '保险': '利率敏感，负债端改善',
        '房地产': '政策预期驱动',
        '白酒': '消费龙头，确定性高',
        '医药生物': '创新药+医疗消费',
        '新能源': '双碳目标，长期赛道',
        '半导体': '国产替代，自主可控',
        '人工智能': '产业爆发，政策利好',
        '汽车整车': '新能源汽车出海',
        '电池': '动力电池龙头',
        '光伏设备': '装机量增长，技术迭代',
    }
    
    for s in sectors:
        s['desc'] = descriptions.get(s['name'], '热门板块')
    
    return jsonify({'success': True, 'data': sectors[:10]})


@app.route('/api/sector-stocks')
def api_sector_stocks():
    """获取板块成分股"""
    sector_code = request.args.get('code', '').strip()
    limit = int(request.args.get('limit', 10))
    
    if not sector_code:
        return jsonify({'success': False, 'message': '请输入板块代码'})
    
    stocks = get_sector_stocks(sector_code, limit)
    return jsonify({'success': True, 'data': stocks})


@app.route('/api/recommend')
def api_recommend():
    """获取推荐股票（基于涨幅和市值筛选）"""
    # 获取几个热门板块的龙头股
    sectors = get_sector_list()
    
    recommend_stocks = []
    seen_codes = set()
    
    # 从涨幅前几的板块中各选1-2只龙头
    for sector in sectors[:5]:
        stocks = get_sector_stocks(sector['code'], 3)
        # 选市值较大的作为龙头
        for stock in stocks:
            if stock['code'] not in seen_codes and stock['price'] > 0:
                seen_codes.add(stock['code'])
                # 获取详细行情
                quote = get_stock_quote(stock['code'])
                if quote:
                    recommend_stocks.append({
                        'code': stock['code'],
                        'name': stock['name'],
                        'price': stock['price'],
                        'change': stock['change'],
                        'sector': sector['name'],
                        'reason': f'{sector["name"]}板块龙头，{sector["desc"] if sector.get("desc") else "行业领先"}',
                        'marketCap': quote.get('totalMarketCap', 0),
                        'pe': quote.get('pe', 0),
                    })
                    if len(recommend_stocks) >= 6:
                        break
        if len(recommend_stocks) >= 6:
            break
    
    # 按市值排序，选龙头
    recommend_stocks.sort(key=lambda x: x.get('marketCap', 0), reverse=True)
    
    # 添加星级评级
    for i, stock in enumerate(recommend_stocks[:6]):
        if i < 2:
            stock['rating'] = 5
            stock['ratingLabel'] = '强烈推荐'
        elif i < 4:
            stock['rating'] = 4
            stock['ratingLabel'] = '推荐'
        else:
            stock['rating'] = 4
            stock['ratingLabel'] = '推荐'
    
    return jsonify({'success': True, 'data': recommend_stocks[:6]})


@app.route('/api/financial')
def api_financial():
    """获取财务数据"""
    code = request.args.get('code', '').strip()
    code = ''.join(filter(str.isdigit, code))
    
    if not code:
        return jsonify({'success': False, 'message': '股票代码格式错误'})
    
    records = get_financial_data(code)
    return jsonify({'success': True, 'data': records})


@app.route('/api/analysis')
def api_analysis():
    """获取个股综合分析"""
    code = request.args.get('code', '').strip()
    code = ''.join(filter(str.isdigit, code))
    
    if not code:
        return jsonify({'success': False, 'message': '股票代码格式错误'})
    
    # 获取行情和K线
    klines = get_kline_data(code, klt=101, lmt=120)
    
    # 优先获取实时行情，如果失败则从K线数据中提取
    quote = get_stock_quote(code)
    if not quote and klines:
        # 从K线数据构建基本行情
        last_kline = klines[-1]
        quote = {
            'code': code,
            'name': code,  # 后面会更新
            'price': last_kline['close'],
            'change': 0,
            'changeAmount': 0,
            'open': last_kline['open'],
            'high': last_kline['high'],
            'low': last_kline['low'],
            'preClose': last_kline['close'],
            'volume': last_kline['volume'],
            'amount': last_kline['amount'],
            'turnover': 0,
            'amplitude': 0,
            'pe': 0,
            'pb': 0,
            'totalMarketCap': 0,
            'floatMarketCap': 0,
            'volumeRatio': 0,
            'fromKline': True
        }
    
    if not quote or not klines:
        return jsonify({'success': False, 'message': '获取数据失败'})
    
    # 生成分析
    analysis = generate_analysis(quote, klines)
    
    # 获取财务数据
    financial = get_financial_data(code)
    
    return jsonify({
        'success': True,
        'data': {
            'quote': quote,
            'klines': klines[-60:],  # 返回最近60根K线
            'analysis': analysis,
            'financial': financial,
            'updateTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    })


@app.route('/api/news')
def api_news():
    """获取市场新闻（使用东方财富财经要闻）"""
    url = 'https://np-listapi.eastmoney.com/comm/wap/getListInfo?cb=callback&client=wap&type=1&mTypeAndCol=1_70&pageSize=10&pageIndex=0'
    
    try:
        resp = requests.get(url, headers=HEADERS_EASTMONEY, timeout=10)
        text = resp.text
        # 解析JSONP
        if text.startswith('callback('):
            text = text[len('callback('):-1]
        data = json.loads(text)
        news = []
        if data.get('data') and data['data'].get('list'):
            for item in data['data']['list'][:8]:
                news.append({
                    'title': item.get('Title', ''),
                    'time': item.get('ShowTime', ''),
                    'source': item.get('MediaName', '东方财富'),
                    'tag': item.get('Column', '财经'),
                    'url': item.get('Url', '')
                })
        return jsonify({'success': True, 'data': news})
    except Exception as e:
        print(f'获取新闻失败: {e}')
        # 返回备用新闻
        return jsonify({'success': True, 'data': [
            {'title': 'A股市场震荡上行，成交量持续放大', 'time': '今日', 'source': '财经要闻', 'tag': '市场'},
            {'title': '科技板块领涨，AI概念持续活跃', 'time': '今日', 'source': '财经要闻', 'tag': '科技'},
            {'title': '新能源汽车销量创新高，渗透率突破40%', 'time': '昨日', 'source': '行业资讯', 'tag': '行业'},
            {'title': '外资持续流入，北上资金净买入超百亿', 'time': '昨日', 'source': '资金流向', 'tag': '资金'},
        ]})


# ==================== 启动 ====================

if __name__ == '__main__':
    print('=' * 50)
    print('  智投分析 - 股票分析后端服务')
    print('  服务地址: http://localhost:5000')
    print('  数据源: 东方财富公开API')
    print('=' * 50)
    print()
    app.run(host='0.0.0.0', port=5000, debug=False)

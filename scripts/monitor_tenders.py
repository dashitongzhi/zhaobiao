#!/usr/bin/env python3
"""
招标信息监控爬虫
功能：从多个政府招标平台自动抓取招标公告，过滤符合条件的项目
数据源：中国政府采购网(ccgp.gov.cn)、全国公共资源交易平台(ggzy.gov.cn)

Usage:
    python monitor_tenders.py --keywords IT --budget-min 100000 --budget-max 5000000
"""

import argparse
import json
import logging
import time
import re
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# 数据模型
# ============================================================

@dataclass
class TenderInfo:
    """招标信息数据结构"""
    title: str                    # 招标项目名称
    source: str                   # 来源平台
    url: str                     # 原始链接
    publish_date: str            # 发布日期
    deadline: str                # 投标截止日期
    budget: Optional[float]      # 预算金额（元）
    region: str                  # 地区/省份
    industry: str                # 行业类别
    tender_type: str             # 招标方式
    qualification: list[str]     # 资质要求
    description: str             # 简要描述
    raw_data: dict               # 原始数据（保留）


# ============================================================
# 配置参数
# ============================================================

TENDER_SOURCES = {
    "ccgp": {
        "name": "中国政府采购网",
        "base_url": "https://www.ccgp.gov.cn",
        "channels": {
            "zygg_gkzb": "/cggg/zygg/gkzb/",      # 中央单位采购公告-公开招标
            "zygg_qtgg": "/cggg/zygg/qtgg/",      # 中央单位采购公告-其他
            "dfgg_gkzb": "/cggg/dfgg/gkzb/",      # 地方单位采购公告-公开招标
            "dfgg_ztb": "/cggg/dfgg/zbgg/",       # 地方单位采购公告-招标公告
        },
    },
    "ggzy": {
        "name": "全国公共资源交易平台",
        "base_url": "https://www.ggzy.gov.cn",
        "channels": {
            "cg_zfcg": "/deal/dealList.html?HEADER_DEAL_TYPE=02",  # 政府采购
        },
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "tenders")


# ============================================================
# 爬虫实现
# ============================================================

def fetch_page(url: str, encoding: str = "utf-8", timeout: int = 15) -> Optional[str]:
    """获取网页内容"""
    try:
        import requests
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.encoding = encoding
        if resp.status_code == 200:
            return resp.text
        else:
            logger.warning(f"HTTP {resp.status_code} for {url}")
            return None
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


def parse_ccgp_list(html: str, base_url: str) -> list[dict]:
    """解析中国政府采购网列表页"""
    from bs4 import BeautifulSoup
    tenders = []
    soup = BeautifulSoup(html, "lxml")
    
    # 查找所有 li 列表项
    for li in soup.find_all("li"):
        a = li.find("a")
        if not a:
            continue
        href = a.get("href", "")
        title = a.get_text(strip=True)
        
        # 跳过导航链接
        if not href or title in ["信息公开", "政采法规", "购买服务", "监督检查", 
                                  "信息公告", "国际专栏", "中央单位采购公告", "地方单位采购公告"]:
            continue
        
        # 解析相对链接为完整链接
        if href.startswith("./"):
            href = base_url + href[1:]
        elif href.startswith("../"):
            href = base_url + href
        
        # 跳过非详情页链接
        if not any(x in href for x in [".htm", "/news/", "/zcdt/", "/gpsr/", "/jdjc/", "/zcfg/"]):
            continue
        if "t20" not in href and ".htm" not in href:
            continue
            
        # 提取日期 - li 中可能包含日期信息
        date_text = ""
        date_spans = li.find_all("span")
        for span in date_spans:
            t = span.get_text(strip=True)
            if re.match(r"\d{4}-\d{2}-\d{2}", t):
                date_text = t
                break
        
        tenders.append({
            "title": title,
            "url": href,
            "publish_date": date_text,
        })
    
    return tenders


def crawl_ccgp(source_config: dict, channel_key: str, channel_path: str) -> list[dict]:
    """抓取中国政府采购网指定频道"""
    base_url = source_config["base_url"]
    url = base_url + channel_path
    logger.info(f"Fetching CCGP: {url}")
    
    html = fetch_page(url)
    if not html:
        return []
    
    tenders = parse_ccgp_list(html, base_url)
    logger.info(f"  Found {len(tenders)} items from {channel_key}")
    
    # 补充来源信息
    for t in tenders:
        t["source"] = "ccgp.gov.cn"
    return tenders


def parse_ggzy_list(html: str, base_url: str) -> list[dict]:
    """解析全国公共资源交易平台列表页"""
    from bs4 import BeautifulSoup
    tenders = []
    soup = BeautifulSoup(html, "lxml")
    
    # 查找数据区域 - 通常在特定的div中
    # 全国公共资源交易平台使用动态加载，尝试查找现有链接
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        title = a.get_text(strip=True)
        
        if not title or len(title) < 5:
            continue
            
        # 跳过站外链接和导航链接
        if href.startswith("http") and "ggzy.gov.cn" not in href:
            continue
        if href.startswith("/SIC/") or href.startswith("/serve/"):
            continue
        if title in ["政府网站工作年度报表", "机构职能", "交易公开", "政策法规", "数据服务"]:
            continue
            
        # 解析相对链接
        if href.startswith("/"):
            href = base_url + href
        elif href.startswith("./"):
            href = base_url + href[1:]
            
        # 查找日期
        date_text = ""
        parent = a.find_parent(["li", "div", "td"])
        if parent:
            text = parent.get_text()
            m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
            if m:
                date_text = m.group(1)
        
        tenders.append({
            "title": title,
            "url": href,
            "publish_date": date_text,
        })
    
    return tenders


def crawl_ggzy(source_config: dict, channel_key: str, channel_path: str) -> list[dict]:
    """抓取全国公共资源交易平台指定频道"""
    base_url = source_config["base_url"]
    url = base_url + channel_path
    logger.info(f"Fetching GGZY: {url}")
    
    html = fetch_page(url)
    if not html:
        return []
    
    tenders = parse_ggzy_list(html, base_url)
    logger.info(f"  Found {len(tenders)} items from {channel_key}")
    
    for t in tenders:
        t["source"] = "ggzy.gov.cn"
    return tenders


def parse_tender_detail(html: str, source: str) -> dict:
    """解析招标详情页，提取更多信息"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    result = {
        "deadline": "",
        "budget": None,
        "region": "",
        "industry": "",
        "tender_type": "",
        "qualification": [],
        "description": "",
    }
    
    text = soup.get_text(separator=" ", strip=True)
    
    # 提取预算金额 - 多种模式
    budget_patterns = [
        r"预算[金额]?[：:]\s*([\d,，.]+)\s*(?:万元|元)",
        r"采购[金额]?[：:]\s*([\d,，.]+)\s*(?:万元|元)",
        r"最高限价[：:]\s*([\d,，.]+)\s*(?:万元|元)",
        r"最高限价[：:]\s*([\d,，.]+)",
        r"预算[金额]?[：:]\s*([\d,，.]+)",
    ]
    for pattern in budget_patterns:
        m = re.search(pattern, text)
        if m:
            amount_str = m.group(1).replace(",", "").replace("，", "")
            try:
                amount = float(amount_str)
                if "万元" in m.group(0):
                    amount *= 10000
                result["budget"] = amount
                break
            except ValueError:
                pass
    
    # 提取截止时间
    deadline_patterns = [
        r"投标截止[时间]?[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2}\s*[^\n]{0,30})",
        r"截止[时间]?[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2}\s*[^\n]{0,30})",
        r"开标[时间]?[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2}\s*[^\n]{0,30})",
    ]
    for pattern in deadline_patterns:
        m = re.search(pattern, text)
        if m:
            result["deadline"] = m.group(1).strip()
            break
    
    # 提取地区
    region_patterns = [
        r"([^\s]{2,8}?(?:省|市|自治区|县|区))\d{4,}",
    ]
    for pattern in region_patterns:
        m = re.search(pattern, text)
        if m:
            result["region"] = m.group(1)[:10]
            break
    
    # 提取招标方式
    if "公开招标" in text:
        result["tender_type"] = "公开招标"
    elif "竞争性磋商" in text:
        result["tender_type"] = "竞争性磋商"
    elif "竞争性谈判" in text:
        result["tender_type"] = "竞争性谈判"
    elif "单一来源" in text:
        result["tender_type"] = "单一来源"
    elif "询价" in text:
        result["tender_type"] = "询价采购"
    
    return result


# ============================================================
# 监控器主类
# ============================================================

class TenderMonitor:
    """招标监控器"""

    def __init__(
        self,
        keywords: list[str] = None,
        budget_min: float = 0,
        budget_max: float = float('inf'),
        regions: list[str] = None,
        industries: list[str] = None,
    ):
        self.keywords = keywords or []
        self.budget_min = budget_min
        self.budget_max = budget_max
        self.regions = regions or []
        self.industries = industries or []
        self.tenders: list[TenderInfo] = []
        self._session_tenders: list[dict] = []

    def crawl_source(self, source_id: str) -> list[dict]:
        """
        抓取指定数据源
        """
        logger.info(f"Crawling source: {source_id}")
        
        if source_id not in TENDER_SOURCES:
            logger.error(f"Unknown source: {source_id}")
            return []
        
        source_config = TENDER_SOURCES[source_id]
        results = []
        
        if source_id == "ccgp":
            for channel_key, channel_path in source_config["channels"].items():
                items = crawl_ccgp(source_config, channel_key, channel_path)
                results.extend(items)
                time.sleep(0.5)  # 礼貌爬取
                
        elif source_id == "ggzy":
            for channel_key, channel_path in source_config["channels"].items():
                items = crawl_ggzy(source_config, channel_key, channel_path)
                results.extend(items)
                time.sleep(0.5)
        
        logger.info(f"Total items from {source_id}: {len(results)}")
        return results

    def filter_tender(self, tender: dict) -> bool:
        """
        根据筛选条件过滤招标信息
        """
        # 关键词匹配
        if self.keywords:
            title = tender.get("title", "")
            if not any(kw.lower() in title.lower() for kw in self.keywords):
                return False

        # 预算金额过滤
        budget = tender.get("budget")
        if budget is not None:
            if budget < self.budget_min or budget > self.budget_max:
                return False

        return True

    def save_results(self, output_file: str = None) -> str:
        """
        保存结果到JSON文件
        """
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(OUTPUT_DIR, f"tenders_{timestamp}.json")

        output = {
            "fetch_time": datetime.now().isoformat(),
            "total_count": len(self.tenders),
            "filters": {
                "keywords": self.keywords,
                "budget_range": [self.budget_min, self.budget_max],
                "regions": self.regions,
                "industries": self.industries,
            },
            "tenders": [
                {
                    "title": t.title,
                    "source": t.source,
                    "url": t.url,
                    "publish_date": t.publish_date,
                    "deadline": t.deadline,
                    "budget": t.budget,
                    "region": t.region,
                }
                for t in self.tenders
            ]
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(self.tenders)} tenders to {output_file}")
        return output_file

    def run(self) -> list[TenderInfo]:
        """运行完整爬取流程"""
        for source_id in TENDER_SOURCES:
            try:
                data = self.crawl_source(source_id)
                for item in data:
                    # 填充默认值
                    item.setdefault("deadline", "")
                    item.setdefault("budget", None)
                    item.setdefault("region", "")
                    item.setdefault("industry", "")
                    item.setdefault("tender_type", "")
                    item.setdefault("qualification", [])
                    item.setdefault("description", item.get("title", ""))
                    item.setdefault("raw_data", item.copy())
                    
                    if self.filter_tender(item):
                        self.tenders.append(TenderInfo(**item))
            except Exception as e:
                logger.error(f"Error crawling {source_id}: {e}")
        
        return self.tenders


# ============================================================
# CLI入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="招标信息监控爬虫")
    parser.add_argument("--keywords", nargs="+", help="关键词列表")
    parser.add_argument("--budget-min", type=float, default=0, help="最小预算金额")
    parser.add_argument("--budget-max", type=float, default=float('inf'), help="最大预算金额")
    parser.add_argument("--regions", nargs="+", help="地区列表")
    parser.add_argument("--industries", nargs="+", help="行业列表")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--list-only", action="store_true", help="仅列出抓取的URL，不保存")

    args = parser.parse_args()

    monitor = TenderMonitor(
        keywords=args.keywords,
        budget_min=args.budget_min,
        budget_max=args.budget_max,
        regions=args.regions,
        industries=args.industries,
    )

    # 遍历所有数据源
    for source_id in TENDER_SOURCES:
        try:
            data = monitor.crawl_source(source_id)
            logger.info(f"Fetched {len(data)} items from {source_id}")
            for item in data:
                if monitor.filter_tender(item):
                    item.setdefault("deadline", "")
                    item.setdefault("budget", None)
                    item.setdefault("region", "")
                    item.setdefault("industry", "")
                    item.setdefault("tender_type", "")
                    item.setdefault("qualification", [])
                    item.setdefault("description", item.get("title", ""))
                    item.setdefault("raw_data", item.copy())
                    monitor.tenders.append(TenderInfo(**item))
        except Exception as e:
            logger.error(f"Error crawling {source_id}: {e}")

    if args.list_only:
        for t in monitor.tenders:
            print(f"[{t.source}] {t.publish_date} | {t.title}")
            print(f"  URL: {t.url}")
            if t.budget:
                print(f"  预算: {t.budget:,.0f}元")
            print()
        print(f"Total: {len(monitor.tenders)} tenders")
    else:
        output_file = monitor.save_results(args.output)
        print(f"Results saved to: {output_file}")
        print(f"Total tenders collected: {len(monitor.tenders)}")


if __name__ == "__main__":
    main()
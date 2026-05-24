#!/usr/bin/env python3
"""
评标打分辅助工具
功能：根据评标标准对我方投标文件自评，或分析中标/未中标原因

Usage:
    python score_evaluation.py --bid-file technical_proposal.md --criteria-file evaluation_criteria.json
"""

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# ============================================================
# 数据模型
# ============================================================

@dataclass
class Criterion:
    """评标标准项"""
    id: str
    name: str
    weight: float          # 权重（0-1）
    max_score: float       # 满分
    description: str       # 评分说明
    score: Optional[float] = None  # 我方得分
    evidence: str = ""      # 评分依据


@dataclass
class EvaluationResult:
    """评标结果"""
    total_score: float
    technical_score: float
    price_score: float
    rank: Optional[int] = None
    competitors: list[dict] = None  # [{name, score, rank}]

    def get_winning_probability(self) -> float:
        """估算中标概率"""
        if not self.competitors:
            return 0.5  # 未知情况下默认为50%
        my_score = self.total_score
        higher_count = sum(1 for c in self.competitors if c["score"] > my_score)
        return (len(self.competitors) - higher_count) / (len(self.competitors) + 1)


# ============================================================
# 评标辅助工具
# ============================================================

class EvaluationScorer:
    """评标打分辅助"""

    def __init__(self, criteria: list[Criterion]):
        self.criteria = criteria
        self.technical_weight = 0.7      # 技术分权重
        self.price_weight = 0.3           # 价格分权重
        self.price_base = 0               # 基准价（最低价）

    def set_weights(self, tech: float, price: float):
        """设置技术/价格权重"""
        self.technical_weight = tech
        self.price_weight = price

    def set_price_base(self, price: float):
        """设置基准价（用于价格分计算）"""
        self.price_base = price

    def score_criterion(self, criterion_id: str, score: float, evidence: str = ""):
        """
        对某个标准项打分
        """
        for c in self.criteria:
            if c.id == criterion_id:
                if score > c.max_score:
                    score = c.max_score
                c.score = score
                c.evidence = evidence
                break

    def calculate_technical_score(self) -> float:
        """计算技术分"""
        total_weighted = 0
        total_weight = 0

        for c in self.criteria:
            if c.score is not None:
                normalized = c.score / c.max_score
                total_weighted += normalized * c.weight
                total_weight += c.weight

        if total_weight == 0:
            return 0

        return total_weighted / total_weight * 100  # 百分制

    def calculate_price_score(self, my_price: float) -> float:
        """
        计算价格分（最低价法）
        价格分 = (基准价 / 投标价) × 满分
        """
        if self.price_base == 0 or my_price == 0:
            return 0

        return (self.price_base / my_price) * 100

    def evaluate(self, my_price: float) -> EvaluationResult:
        """
        综合评标
        """
        tech_score = self.calculate_technical_score()
        price_score = self.calculate_price_score(my_price)

        total = tech_score * self.technical_weight + price_score * self.price_weight

        return EvaluationResult(
            total_score=total,
            technical_score=tech_score,
            price_score=price_score,
            competitors=[]
        )

    def analyze_gap(self, target_score: float) -> list[dict]:
        """
        分析与目标分的差距
        """
        gaps = []
        current_score = self.calculate_technical_score()

        for c in self.criteria:
            if c.score is not None:
                gap_score = (target_score * c.weight) - (c.score / c.max_score * c.weight * 100)
                if gap_score > 0:
                    gaps.append({
                        "criterion": c.name,
                        "gap": gap_score,
                        "suggestion": f"需要提升{c.name}的得分"
                    })

        return sorted(gaps, key=lambda x: x["gap"], reverse=True)

    def generate_report(self, result: EvaluationResult) -> str:
        """
        生成评标分析报告
        """
        report = "# 评标分析报告\n\n"
        report += f"**生成时间**：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}\n\n"
        report += "---\n\n"

        report += "## 综合评分\n\n"
        report += f"- **总分**：{result.total_score:.2f}分\n"
        report += f"- **技术分**：{result.technical_score:.2f}分（权重{self.technical_weight*100:.0f}%）\n"
        report += f"- **价格分**：{result.price_score:.2f}分（权重{self.price_weight*100:.0f}%）\n\n"

        if result.competitors:
            report += f"- **排名**：第{result.rank}名（共{len(result.competitors)+1}家）\n"
            report += f"- **中标概率**：{result.get_winning_probability()*100:.1f}%\n\n"

        report += "## 分项得分明细\n\n"
        report += "| 序号 | 评审项 | 权重 | 满分 | 得分 | 得分率 |\n"
        report += "|-----|-------|-----|-----|------|-------|\n"

        for i, c in enumerate(self.criteria, 1):
            if c.score is not None:
                rate = c.score / c.max_score * 100
                report += f"| {i} | {c.name} | {c.weight*100:.0f}% | {c.max_score} | {c.score:.1f} | {rate:.1f}% |\n"

        report += "\n## 评分依据\n\n"
        for c in self.criteria:
            if c.score is not None:
                report += f"### {c.name}\n"
                report += f"{c.evidence}\n\n"

        # 差距分析
        if result.rank and result.rank > 1:
            report += "## 改进建议\n\n"
            gaps = self.analyze_gap(result.total_score / len(self.criteria))
            for gap in gaps[:5]:  # Top 5改进项
                report += f"- **{gap['criterion']}**：{gap['suggestion']}\n"

        return report


# ============================================================
# 增强评标打分器（实现真实打分逻辑）
# ============================================================

@dataclass
class ScoredCriterion(Criterion):
    """带自动评分结果的评标项"""
    scoring_keywords: list[str] = field(default_factory=list)  # 触发满分的关键词
    partial_keywords: list[str] = field(default_factory=list)   # 触发部分得分的关键词
    auto_score: Optional[float] = None                         # 自动评分结果


class BidParser:
    """投标文件解析器"""

    # 常见评分关键词映射
    KEYWORD_SCORE_MAP = {
        # 完整性相关
        "需求分析": 1.0, "需求理解": 1.0, "响应": 0.8,
        "方案设计": 1.0, "设计方案": 1.0, "架构": 0.9,
        "实施": 0.8, "实施计划": 1.0, "进度": 0.8,
        "质量": 0.9, "质量保证": 1.0, "ISO": 1.0,
        "售后": 0.9, "服务承诺": 1.0, "维护": 0.8,
        "案例": 0.8, "业绩": 0.9, "经验": 0.8,
        "团队": 0.8, "项目经理": 0.7, "技术负责人": 0.7,
        # 价格相关
        "报价": 0.7, "价格合理": 1.0, "成本": 0.8,
        "分项报价": 1.0, "总价": 0.8,
        # 资质相关
        "资质": 0.9, "证书": 0.8, "认证": 0.9,
        "ISO9001": 1.0, "ISO27001": 1.0, "CMMI": 1.0,
        # 技术能力
        "网络安全": 0.9, "等保": 1.0, "三级": 1.0,
        "云平台": 0.8, "大数据": 0.8, "AI": 0.7,
        "物联网": 0.7, "智能化": 0.7,
    }

    def __init__(self, bid_content: str):
        self.content = bid_content
        self.lines = bid_content.split('\n')

    def extract_section(self, section_name: str) -> str:
        """提取指定章节内容"""
        pattern = rf'(?:^|\n)#{1,6}\s*{re.escape(section_name)}.*?(?=(?:^#{1,6}\s)|\Z)'
        match = re.search(pattern, self.content, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(0)
        return ""

    def search_keywords(self, keywords: list[str]) -> dict:
        """搜索关键词并返回匹配结果"""
        results = {}
        for kw in keywords:
            # 搜索关键词（支持中英文和变体）
            pattern = re.compile(rf'{re.escape(kw)}', re.IGNORECASE)
            matches = pattern.findall(self.content)
            if matches:
                results[kw] = len(matches)
        return results

    def get_relevance_score(self, criterion_name: str, keywords: list[str] = None) -> tuple[float, str]:
        """
        根据内容相关性计算得分
        
        Returns:
            (score_ratio, evidence): 得分比例(0-1)和评分依据
        """
        if keywords is None:
            # 自动生成关键词
            keywords = list(self.KEYWORD_SCORE_MAP.keys())

        matched = self.search_keywords(keywords)
        if not matched:
            return 0.0, "未找到相关响应内容"

        # 计算总权重
        total_weight = sum(self.KEYWORD_SCORE_MAP.get(kw, 0.5) for kw in matched.keys())
        max_possible = sum(self.KEYWORD_SCORE_MAP.get(kw, 0.5) for kw in keywords if kw in self.KEYWORD_SCORE_MAP)

        if max_possible == 0:
            return 0.5, f"找到{sum(matched.values())}处相关描述"

        score_ratio = min(1.0, total_weight / max_possible * len(matched))
        evidence = f"匹配到: {', '.join(f'{k}({v}处)' for k, v in matched.items())}"

        return score_ratio, evidence

    def extract_price(self) -> Optional[float]:
        """从投标文件中提取报价"""
        # 尝试多种报价提取模式
        patterns = [
            r'报价[：:]\s*[:：]?\s*([¥￥$]?\s*\d+(?:\.\d+)?)\s*(?:万元|万)?',
            r'投标总价[：:]\s*([¥￥$]?\s*\d+(?:\.\d+)?)\s*(?:万元|万)?',
            r'合同金额[：:]\s*([¥￥$]?\s*\d+(?:\.\d+)?)\s*(?:万元|万)?',
            r'总报价[：:]\s*([¥￥$]?\s*\d+(?:\.\d+)?)\s*(?:万元|万)?',
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content)
            if match:
                price_str = match.group(1).replace('¥', '').replace('￥', '').replace('$', '').replace(',', '').strip()
                try:
                    price = float(price_str)
                    # 如果金额过小，可能是忘了写万
                    if price < 1000:
                        price *= 10000
                    return price
                except ValueError:
                    continue

        return None

    def extract_company_info(self) -> dict:
        """提取企业信息"""
        info = {}

        # 提取公司名称
        name_patterns = [
            r'投标单位[：:]\s*([^\n]+)',
            r'公司名称[：:]\s*([^\n]+)',
            r'单位名称[：:]\s*([^\n]+)',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, self.content)
            if match:
                info['company_name'] = match.group(1).strip()
                break

        # 提取联系人
        contact_patterns = [
            r'联系人[：:]\s*([^\n]+)',
            r'联系 人[：:]\s*([^\n]+)',
        ]
        for pattern in contact_patterns:
            match = re.search(pattern, self.content)
            if match:
                info['contact'] = match.group(1).strip()
                break

        # 提取电话
        phone_pattern = r'电话[：:]?\s*([\d\-]+)'
        match = re.search(phone_pattern, self.content)
        if match:
            info['phone'] = match.group(1).strip()

        return info


class CriteriaParser:
    """评标标准解析器"""

    @staticmethod
    def parse_from_json(criteria_json: list[dict]) -> list[Criterion]:
        """从JSON解析评标标准"""
        criteria = []
        for item in criteria_json:
            criterion = Criterion(
                id=item.get('id', ''),
                name=item.get('name', ''),
                weight=item.get('weight', 0.0),
                max_score=item.get('max_score', 100.0),
                description=item.get('description', ''),
                score=item.get('score'),
                evidence=item.get('evidence', '')
            )
            criteria.append(criterion)
        return criteria

    @staticmethod
    def parse_from_markdown(md_content: str) -> list[Criterion]:
        """
        从Markdown评标标准文档解析
        支持格式:
        ## 技术方案完整性 (20-30分)
        - 需求理解与响应
        - 方案设计逻辑性
        """
        criteria = []
        # 匹配形如 "## 评审项名称 (权重分)" 的模式
        pattern = r'##\s+([^\n]+?)\s*\((\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\s*分?\)'

        for match in re.finditer(pattern, md_content):
            name = match.group(1).strip()
            min_score = float(match.group(2))
            max_score = float(match.group(3))
            weight = min_score / 100.0  # 假设满分100，权重就是最低分

            criterion = Criterion(
                id=name.replace(' ', '_').lower(),
                name=name,
                weight=weight,
                max_score=max_score,
                description=""
            )
            criteria.append(criterion)

        return criteria

    @staticmethod
    def generate_default_criteria() -> list[Criterion]:
        """生成默认评标标准（当无法解析时使用）"""
        return [
            Criterion(
                id="tech_completeness",
                name="技术方案完整性",
                weight=0.25,
                max_score=100,
                description="需求理解、方案设计、实施方法的完整性和可行性"
            ),
            Criterion(
                id="enterprise_qualification",
                name="企业资质与业绩",
                weight=0.20,
                max_score=100,
                description="类似项目经验、资质证书等级、团队配置"
            ),
            Criterion(
                id="quality_assurance",
                name="质量保证措施",
                weight=0.15,
                max_score=100,
                description="质量管理体系、验收标准、售后服务承诺"
            ),
            Criterion(
                id="schedule_progress",
                name="工期与进度",
                weight=0.15,
                max_score=100,
                description="进度计划合理性、里程碑设置、风险预案"
            ),
            Criterion(
                id="price_reasonableness",
                name="报价合理性",
                weight=0.25,
                max_score=100,
                description="总价合理性、分项报价透明性、成本结构清晰度"
            ),
        ]


class EnhancedEvaluationScorer(EvaluationScorer):
    """
    增强版评标打分器
    实现真实打分逻辑：
    1. 自动解析招标文件中的评标标准
    2. 自动匹配我方投标文件响应内容
    3. 智能计算各项得分
    4. 生成完整评标报告
    """

    def __init__(self, criteria: list[Criterion] = None):
        super().__init__(criteria or [])
        self.bid_parser: Optional[BidParser] = None
        self.price_base = 0  # 基准价
        self.my_price = 0    # 我方报价

    def load_criteria_from_file(self, file_path: str):
        """从文件加载评标标准"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if file_path.endswith('.json'):
            data = json.loads(content)
            self.criteria = CriteriaParser.parse_from_json(data)
        elif file_path.endswith('.md'):
            self.criteria = CriteriaParser.parse_from_markdown(content)
        else:
            # 尝试JSON格式，不行则用Markdown解析
            try:
                data = json.loads(content)
                self.criteria = CriteriaParser.parse_from_json(data)
            except json.JSONDecodeError:
                self.criteria = CriteriaParser.parse_from_markdown(content)

        # 如果解析失败，使用默认标准
        if not self.criteria:
            self.criteria = CriteriaParser.generate_default_criteria()

    def load_bid_from_file(self, file_path: str):
        """加载投标文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.bid_parser = BidParser(content)
        # 自动提取报价
        self.my_price = self.bid_parser.extract_price() or 0

    def auto_score_all(self):
        """
        自动对所有评标项打分
        根据我方投标文件内容，匹配并计算每项得分
        """
        if not self.bid_parser:
            return

        for criterion in self.criteria:
            self._auto_score_criterion(criterion)

    def _auto_score_criterion(self, criterion: Criterion):
        """
        自动评估单个评标项

        评分策略：
        1. 根据评标项名称和相关关键词搜索投标文件
        2. 匹配到则根据匹配程度计算得分
        3. 未匹配到则得0分
        """
        # 准备搜索关键词
        keywords = self._get_criterion_keywords(criterion)

        # 获取相关内容进行评分
        score_ratio, evidence = self.bid_parser.get_relevance_score(
            criterion.name,
            keywords
        )

        # 计算实际得分
        actual_score = round(score_ratio * criterion.max_score, 1)

        # 更新评标项
        criterion.score = actual_score
        criterion.evidence = evidence

    def _get_criterion_keywords(self, criterion: Criterion) -> list[str]:
        """根据评标项获取应搜索的关键词"""
        # 关键词映射表
        keyword_map = {
            "技术方案完整性": ["需求分析", "需求理解", "方案设计", "架构", "实施", "进度"],
            "企业资质与业绩": ["资质", "证书", "案例", "业绩", "经验", "团队"],
            "质量保证措施": ["质量", "ISO", "验收", "售后", "服务", "维护"],
            "工期与进度": ["工期", "进度", "里程碑", "计划", "周期"],
            "报价合理性": ["报价", "价格", "成本", "分项", "总价"],
        }

        # 从描述中提取关键词
        desc_keywords = re.findall(r'[\u4e00-\u9fa5]{2,}', criterion.description)

        # 合并并去重
        base_keywords = keyword_map.get(criterion.name, [])
        all_keywords = list(set(base_keywords + desc_keywords))

        return all_keywords if all_keywords else list(BidParser.KEYWORD_SCORE_MAP.keys())

    def calculate_technical_score(self) -> float:
        """计算技术分（加权平均）"""
        if not self.criteria:
            return 0

        total_weighted = 0
        total_weight = 0

        for c in self.criteria:
            if c.score is not None:
                # 归一化得分 = 实际得分 / 满分
                normalized = c.score / c.max_score
                total_weighted += normalized * c.weight
                total_weight += c.weight

        if total_weight == 0:
            return 0

        # 返回加权平均分的百分制
        return (total_weighted / total_weight) * 100

    def calculate_price_score(self, my_price: float = None) -> float:
        """
        计算价格分（最低价法）

        公式: 价格分 = (基准价 / 投标价) × 100
        当投标价为最低价时，价格分满分100
        """
        price = my_price or self.my_price

        if self.price_base <= 0 or price <= 0:
            # 如果没有基准价，按已知的最低价计算
            return 100.0 if price > 0 else 0

        return (self.price_base / price) * 100

    def evaluate(self, my_price: float = None, competitors: list[dict] = None) -> EvaluationResult:
        """
        综合评标

        Args:
            my_price: 我方报价（如果不提供则从投标文件中提取）
            competitors: 竞争对手得分列表 [{name, score, rank}, ...]

        Returns:
            EvaluationResult: 包含所有评分结果和中标概率
        """
        price = my_price or self.my_price

        # 技术分
        tech_score = self.calculate_technical_score()

        # 价格分
        price_score = self.calculate_price_score(price)

        # 综合得分
        total = tech_score * self.technical_weight + price_score * self.price_weight

        # 处理竞争对手数据
        competitor_list = competitors or []

        # 计算排名
        rank = None
        if competitor_list:
            all_scores = [(c['score'], c.get('name', '未知')) for c in competitor_list]
            all_scores.append((total, '我方'))
            sorted_scores = sorted(all_scores, key=lambda x: x[0], reverse=True)

            for idx, (_, name) in enumerate(sorted_scores, 1):
                if name == '我方':
                    rank = idx
                    break

        result = EvaluationResult(
            total_score=round(total, 2),
            technical_score=round(tech_score, 2),
            price_score=round(price_score, 2),
            rank=rank,
            competitors=competitor_list
        )

        return result

    def generate_report(self, result: EvaluationResult, show_improvements: bool = True) -> str:
        """
        生成详细的评标分析报告（支持Markdown格式）
        """
        report = "# 评标分析报告\n\n"
        report += f"**生成时间**：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}\n\n"
        report += "---\n\n"

        # 综合评分
        report += "## 综合评分\n\n"
        report += f"- **总分**：{result.total_score:.2f}分\n"
        report += f"- **技术分**：{result.technical_score:.2f}分（权重{self.technical_weight*100:.0f}%）\n"
        report += f"- **价格分**：{result.price_score:.2f}分（权重{self.price_weight*100:.0f}%）\n"

        if result.rank:
            report += f"- **排名**：第{result.rank}名（共{len(result.competitors)+1}家参与排名）\n"
            report += f"- **中标概率**：{result.get_winning_probability()*100:.1f}%\n"

        report += "\n"

        # 分项得分明细
        report += "## 分项得分明细\n\n"
        report += "| 序号 | 评审项 | 权重 | 满分 | 得分 | 得分率 | 评分依据 |\n"
        report += "|-----|-------|-----|-----|------|-------|----------|\n"

        scored_criteria = [(c.id, c.name, c.weight, c.max_score, c.score, c.evidence)
                          for c in self.criteria if c.score is not None]

        for i, (cid, name, weight, max_score, score, evidence) in enumerate(scored_criteria, 1):
            if score is not None:
                rate = score / max_score * 100
                # 截断过长的评分依据
                short_evidence = (evidence[:40] + '...') if len(evidence) > 40 else evidence
                report += f"| {i} | {name} | {weight*100:.0f}% | {max_score:.0f} | {score:.1f} | {rate:.1f}% | {short_evidence} |\n"

        report += "\n"

        # 评分依据详情
        report += "## 评分依据详情\n\n"
        for c in self.criteria:
            if c.score is not None:
                report += f"### {c.name} (得分: {c.score:.1f}/{c.max_score:.0f})\n"
                report += f"{c.evidence}\n\n"

        # 改进建议
        if show_improvements and result.rank and result.rank > 1:
            report += "## 改进建议\n\n"
            gaps = self.analyze_gap(result.total_score / max(len(self.criteria), 1))
            for gap in gaps[:5]:
                report += f"- **{gap['criterion']}**：{gap['suggestion']}（差距: {gap['gap']:.2f}分）\n"
            report += "\n"

        # 竞争力分析
        if result.competitors:
            report += "## 竞争力分析\n\n"
            my_score = result.total_score
            for comp in result.competitors:
                diff = my_score - comp.get('score', 0)
                status = "领先" if diff > 0 else "落后" if diff < 0 else "持平"
                report += f"- vs {comp.get('name', '竞争对手')}: {status} {abs(diff):.2f}分\n"
            report += "\n"

        return report

    def analyze_gap(self, target_score: float) -> list[dict]:
        """
        分析与目标分的差距，返回改进建议

        Args:
            target_score: 目标分数

        Returns:
            差距分析列表，按差距大小降序排列
        """
        gaps = []
        current_tech_score = self.calculate_technical_score()

        for c in self.criteria:
            if c.score is not None:
                # 该项满分应得分
                full_weighted_score = (c.max_score / 100) * c.weight * 100
                # 该项实际得分
                actual_weighted = (c.score / c.max_score) * c.weight * 100
                # 差距
                gap = full_weighted_score - actual_weighted

                if gap > 0:
                    # 生成改进建议
                    if c.score / c.max_score < 0.5:
                        suggestion = f"建议大幅增强{c.name}相关内容，需补充详细实施措施和证明材料"
                    elif c.score / c.max_score < 0.8:
                        suggestion = f"建议优化{c.name}方案，增加细节描述和量化指标"
                    else:
                        suggestion = f"可进一步突出{c.name}优势，争取满分"

                    gaps.append({
                        "criterion": c.name,
                        "gap": gap,
                        "current_score": c.score,
                        "max_score": c.max_score,
                        "suggestion": suggestion
                    })

        return sorted(gaps, key=lambda x: x["gap"], reverse=True)

    def get_winning_probability(self, competitors: list[dict] = None) -> float:
        """
        计算中标概率

        公式: P(中标) = 排名靠前的投标人家数 / 总投标人家数
            = (总家数 - 比我们分数高的家数) / 总家数
        """
        comp_list = competitors or self.competitors or []

        if not comp_list:
            return 0.5  # 无竞争对手信息时，默认50%

        my_score = self.calculate_technical_score() * self.technical_weight + \
                   self.calculate_price_score() * self.price_weight

        higher_count = sum(1 for c in comp_list if c.get('score', 0) > my_score)
        total = len(comp_list) + 1  # 加上我们自己

        return (total - higher_count) / total


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="评标打分辅助工具")
    parser.add_argument("--criteria-file", help="评标标准文件(JSON或MD)")
    parser.add_argument("--bid-file", help="我方投标文件（用于自评）")
    parser.add_argument("--my-price", type=float, help="我方报价（万元）")
    parser.add_argument("--competitors-file", help="竞争对手得分JSON")
    parser.add_argument("--tech-weight", type=float, default=0.7, help="技术分权重（默认0.7）")
    parser.add_argument("--price-weight", type=float, default=0.3, help="价格分权重（默认0.3）")
    parser.add_argument("--price-base", type=float, default=0, help="基准价/最低价（万元）")
    parser.add_argument("-o", "--output", default="evaluation_report.md", help="输出报告路径")

    args = parser.parse_args()

    # 使用增强版打分器
    scorer = EnhancedEvaluationScorer()

    # 设置权重
    scorer.set_weights(args.tech_weight, args.price_weight)

    # 设置基准价
    if args.price_base > 0:
        scorer.price_base = args.price_base

    # 加载评标标准
    if args.criteria_file:
        scorer.load_criteria_from_file(args.criteria_file)
    else:
        # 使用默认标准
        scorer.criteria = CriteriaParser.generate_default_criteria()

    # 加载投标文件并自动打分
    if args.bid_file:
        scorer.load_bid_from_file(args.bid_file)
        scorer.auto_score_all()

    # 如果命令行提供了报价，覆盖文件中的报价
    price = args.my_price if args.my_price else scorer.my_price

    # 加载竞争对手数据
    competitors = []
    if args.competitors_file:
        with open(args.competitors_file, 'r', encoding='utf-8') as f:
            competitors = json.load(f)

    # 计算结果
    result = scorer.evaluate(my_price=price, competitors=competitors)

    # 生成报告
    report = scorer.generate_report(result)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"评标分析报告已生成: {args.output}")
    print(f"综合得分: {result.total_score:.2f}分")
    if result.rank:
        print(f"排名: 第{result.rank}名")
        print(f"中标概率: {result.get_winning_probability()*100:.1f}%")


if __name__ == "__main__":
    main()
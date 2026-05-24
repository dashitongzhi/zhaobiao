#!/usr/bin/env python3
"""
评标打分辅助工具
功能：根据评标标准对我方投标文件自评，或分析中标/未中标原因

Usage:
    python score_evaluation.py --bid-file technical_proposal.md --criteria-file evaluation_criteria.json
"""

import argparse
import json
from dataclasses import dataclass
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
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="评标打分辅助")
    parser.add_argument("--criteria-file", required=True, help="评标标准JSON文件")
    parser.add_argument("--bid-file", help="我方投标文件（用于自评）")
    parser.add_argument("--my-price", type=float, help="我方报价")
    parser.add_argument("--competitors-file", help="竞争对手得分JSON")
    parser.add_argument("--output", "-o", default="evaluation_report.md", help="输出报告路径")

    args = parser.parse_args()

    # 加载评标标准
    with open(args.criteria_file, 'r', encoding='utf-8') as f:
        criteria_data = json.load(f)
        criteria = [Criterion(**c) for c in criteria_data]

    scorer = EvaluationScorer(criteria)

    # 如果提供了投标文件，需要解析并打分（简化实现）
    if args.bid_file:
        # TODO: 解析投标文件内容，匹配评标项
        pass

    # 如果提供了竞争对手数据
    if args.competitors_file:
        with open(args.competitors_file, 'r', encoding='utf-8') as f:
            competitors = json.load(f)

    # 计算结果
    result = scorer.evaluate(args.my_price or 0)
    result.competitors = competitors if args.competitors_file else []

    # 生成报告
    report = scorer.generate_report(result)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"Evaluation report saved to: {args.output}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
合同关键条款提取器
功能：从合同文档中提取关键条款，生成摘要

Usage:
    python extract_contract.py --contract-file contract.pdf --output contract_summary.md
"""

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# ============================================================
# 数据模型
# ============================================================

@dataclass
class ContractClause:
    """合同条款"""
    clause_type: str      # 条款类型
    title: str             # 条款标题
    content: str           # 条款内容
    key_points: list[str]  # 关键要点


@dataclass
class ContractSummary:
    """合同摘要"""
    contract_name: str
    party_a: str           # 甲方
    party_b: str           # 乙方
    contract_amount: float
    payment_terms: list[dict]
    delivery_terms: str
    acceptance_criteria: str
    warranty_period: str
    penalty_clauses: list[str]
    risk_warnings: list[str]


# ============================================================
# 条款提取器
# ============================================================

class ContractExtractor:
    """合同关键条款提取器"""

    # 关键条款模式（正则表达式）
    CLAUSE_PATTERNS = {
        "金额": r"(合同|合同价款|签约)\s*[金金额][：:]?\s*[,。]?\s*[（(]?\s*[\d,，.]+\s*万元",
        "付款": r"(付款|支付|结算)\s*(条件|方式|节点|时间|比例)",
        "交付": r"(交付|交货|完工|实施)\s*(时间|期限|节点|日期)",
        "验收": r"(验收|交付|竣工)\s*(标准|条件|程序|方式)",
        "质保": r"(质保|质量保证|保修|售后)\s*(期限|时间|范围|条件)",
        "违约金": r"(违约|罚则|罚款|赔偿)\s*(责任|条款|金额|标准)",
        "终止": r"(终止|解除|提前|终止)\s*(合同|条款|条件)",
    }

    # 风险关键词
    RISK_KEYWORDS = [
        "无条件", "不可抗力", "无限责任", "排除", "放弃",
        "单方面", "不对等", "过重", "过短", "模糊",
    ]

    def __init__(self, contract_file: str):
        self.contract_file = contract_file
        self.clauses: list[ContractClause] = []

    def parse_document(self) -> str:
        """
        解析合同文档
        支持PDF/Word/TXT
        """
        if self.contract_file.endswith('.pdf'):
            # TODO: 使用 pdfplumber 或 PyPDF2
            text = ""
        elif self.contract_file.endswith('.docx'):
            # TODO: 使用 python-docx
            text = ""
        else:
            with open(self.contract_file, 'r', encoding='utf-8') as f:
                text = f.read()

        return text

    def extract_clause(self, text: str, clause_type: str, pattern: str) -> Optional[ContractClause]:
        """
        根据模式提取条款
        """
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            content = "\n".join(matches[:5])  # 最多取5条
            return ContractClause(
                clause_type=clause_type,
                title=f"{clause_type}相关条款",
                content=content[:500],  # 截断
                key_points=self._extract_key_points(content)
            )
        return None

    def _extract_key_points(self, content: str) -> list[str]:
        """
        提取关键要点
        """
        points = []
        # 提取数字相关的内容
        numbers = re.findall(r'[\d,，.]+\s*(?:万元|元|天|月|年|%)', content)
        for n in numbers[:5]:
            points.append(n)

        # 提取关键时间节点
        dates = re.findall(r'\d{4}[年-]\d{1,2}[月-]\d{1,2}日?', content)
        for d in dates[:3]:
            points.append(d)

        return points

    def detect_risks(self, text: str) -> list[str]:
        """
        检测合同风险点
        """
        warnings = []
        for keyword in self.RISK_KEYWORDS:
            if keyword in text:
                # 找到包含风险词的段落
                pattern = rf".{{0,30}}{keyword}.{{0,30}}"
                matches = re.findall(pattern, text)
                for m in matches[:2]:
                    warnings.append(m.strip())

        return warnings[:10]  # 最多10条

    def extract_payment_terms(self, text: str) -> list[dict]:
        """
        提取付款条款
        """
        payments = []
        # 查找付款节点模式
        patterns = [
            r"预付款[：:]\s*(\d+)%?\s*[,，]?\s*[金金额]?\s*([\d,，.]+\s*万元)?",
            r"进度款[：:]\s*(\d+)%?\s*[,，]?\s*[金金额]?\s*([\d,，.]+\s*万元)?",
            r"验收款[：:]\s*(\d+)%?\s*[,，]?\s*[金金额]?\s*([\d,，.]+\s*万元)?",
            r"质保金[：:]\s*(\d+)%?\s*[,，]?\s*[金金额]?\s*([\d,，.]+\s*万元)?",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                payments.append({
                    "type": pattern.split('[')[0].strip('^'),
                    "ratio": m[0],
                    "amount": m[1] if len(m) > 1 else ""
                })

        return payments

    def build_summary(self, text: str) -> ContractSummary:
        """
        构建合同摘要
        """
        summary = ContractSummary(
            contract_name="[合同名称待提取]",
            party_a="[甲方待提取]",
            party_b="[乙方待提取]",
            contract_amount=0,
            payment_terms=[],
            delivery_terms="",
            acceptance_criteria="",
            warranty_period="",
            penalty_clauses=[],
            risk_warnings=[]
        )

        # 提取合同名称
        title_match = re.search(r"合同[名称编号][：:]?\s*([^\n]+)", text)
        if title_match:
            summary.contract_name = title_match.group(1).strip()

        # 提取金额
        amount_match = re.search(r"合同价款[：:]\s*([\d,，.]+)\s*(?:万元|元)", text)
        if amount_match:
            amount_str = amount_match.group(1).replace(',', '').replace('，', '')
            summary.contract_amount = float(amount_str)

        # 提取甲乙方
        party_match = re.search(r"甲方[：:]\s*([^\n]+)", text)
        if party_match:
            summary.party_a = party_match.group(1).strip()
        party_match = re.search(r"乙方[：:]\s*([^\n]+)", text)
        if party_match:
            summary.party_b = party_match.group(1).strip()

        # 提取付款条款
        summary.payment_terms = self.extract_payment_terms(text)

        # 提取质保期
        warranty_match = re.search(r"质保期[：:]\s*(\d+)\s*(个月|年|天)", text)
        if warranty_match:
            summary.warranty_period = warranty_match.group(0)

        # 检测风险
        summary.risk_warnings = self.detect_risks(text)

        return summary

    def generate_report(self, summary: ContractSummary, clauses: list[ContractClause]) -> str:
        """
        生成合同分析报告
        """
        report = "# 合同关键条款提取报告\n\n"
        report += f"**生成时间**：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}\n\n"
        report += f"**合同文件**：{self.contract_file}\n\n"
        report += "---\n\n"

        report += "## 基本信息\n\n"
        report += f"- **合同名称**：{summary.contract_name}\n"
        report += f"- **甲方**：{summary.party_a}\n"
        report += f"- **乙方**：{summary.party_b}\n"
        report += f"- **合同金额**：{'¥{:,.2f}'.format(summary.contract_amount) if summary.contract_amount else '[未提取到]'}\n\n"

        report += "## 付款条款\n\n"
        if summary.payment_terms:
            report += "| 付款阶段 | 比例 | 金额 |\n"
            report += "|---------|-----|-----|\n"
            for p in summary.payment_terms:
                report += f"| {p['type']} | {p['ratio']}% | {p.get('amount', '')} |\n"
        else:
            report += "未提取到付款条款\n"
        report += "\n"

        report += "## 质保条款\n\n"
        report += f"{summary.warranty_period or '[未明确]'}\n\n"

        report += "## 关键条款摘要\n\n"
        for clause in clauses:
            report += f"### {clause.title}\n\n"
            report += f"{clause.content}\n\n"

        if summary.risk_warnings:
            report += "---\n\n"
            report += "## ⚠️ 风险预警\n\n"
            for risk in summary.risk_warnings:
                report += f"- {risk}\n"
            report += "\n"

        report += "---\n\n"
        report += "## 建议\n\n"
        report += "1. 仔细核对付款节点与项目里程碑的对应关系\n"
        report += "2. 确认验收标准是否可量化、可操作\n"
        report += "3. 检查违约条款的对等性\n"
        report += "4. 确保质保期限与行业惯例相符\n"

        return report

    def process(self) -> str:
        """
        执行完整提取流程
        """
        text = self.parse_document()
        summary = self.build_summary(text)

        # 提取各类条款
        for clause_type, pattern in self.CLAUSE_PATTERNS.items():
            clause = self.extract_clause(text, clause_type, pattern)
            if clause:
                self.clauses.append(clause)

        return self.generate_report(summary, self.clauses)


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="合同关键条款提取器")
    parser.add_argument("--contract-file", required=True, help="合同文件路径（PDF/Word/TXT）")
    parser.add_argument("--output", "-o", default="contract_summary.md", help="输出文件路径")

    args = parser.parse_args()

    extractor = ContractExtractor(args.contract_file)
    report = extractor.process()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"Contract summary saved to: {args.output}")


if __name__ == "__main__":
    main()
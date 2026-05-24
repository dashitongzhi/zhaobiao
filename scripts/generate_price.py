#!/usr/bin/env python3
"""
商务报价生成器
功能：根据成本估算和竞争策略，生成报价方案

Usage:
    python generate_price.py --budget 5000000 --competitors 3 --output price_bid.md
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
class CostItem:
    """成本项"""
    category: str      # 成本类别（人力/材料/第三方/管理/税金/利润）
    name: str          # 明细名称
    unit: str          # 单位
    quantity: float    # 数量
    unit_price: float  # 单价
    amount: float     # 金额

    def __post_init__(self):
        self.amount = self.quantity * self.unit_price


@dataclass
class PricingStrategy:
    """报价策略"""
    strategy_type: str      # 激进/标准/保守
    margin_ratio: float    # 利润率
    reasoning: str         # 策略说明


# ============================================================
# 报价生成器
# ============================================================

class PriceBidGenerator:
    """商务报价生成器"""

    # 行业利润率参考
    PROFIT_MARGINS = {
        "激进": 0.05,    # 5% 利润
        "标准": 0.10,    # 10% 利润
        "保守": 0.15,    # 15% 利润
    }

    def __init__(
        self,
        budget: float,
        competitors_count: int = 1,
        cost_items: list[CostItem] = None,
    ):
        self.budget = budget
        self.competitors_count = competitors_count
        self.cost_items = cost_items or []
        self.strategies = []

    def add_cost_item(
        self,
        category: str,
        name: str,
        unit: str,
        quantity: float,
        unit_price: float
    ) -> CostItem:
        """添加成本项"""
        item = CostItem(
            category=category,
            name=name,
            unit=unit,
            quantity=quantity,
            unit_price=unit_price,
            amount=0
        )
        self.cost_items.append(item)
        return item

    def calculate_costs(self) -> dict:
        """计算各类成本汇总"""
        totals = {
            "人力成本": 0,
            "材料/设备": 0,
            "第三方服务": 0,
            "管理费用": 0,
            "税金": 0,
            "利润": 0,
        }

        for item in self.cost_items:
            if item.category in totals:
                totals[item.category] += item.amount
            else:
                totals[item.category] = item.amount

        return totals

    def estimate_market_price(self) -> float:
        """
        估算市场价
        基于预算金额和竞争对手数量
        """
        # 简单估算：市场价约为预算的70-85%
        # 实际需结合历史中标数据
        if self.competitors_count >= 5:
            # 竞争激烈，价格可能接近预算
            return self.budget * 0.85
        elif self.competitors_count >= 3:
            return self.budget * 0.80
        else:
            return self.budget * 0.75

    def generate_strategy(self, strategy_type: str) -> PricingStrategy:
        """
        生成指定策略的报价
        """
        cost_total = sum(item.amount for item in self.cost_items)
        margin = self.PROFIT_MARGINS[strategy_type]

        base_price = cost_total / (1 - margin)

        strategy = PricingStrategy(
            strategy_type=strategy_type,
            margin_ratio=margin,
            reasoning=f"基于{strategy_type}策略，利润率{margin*100:.0f}%，含税报价¥{base_price:,.2f}"
        )
        strategy.price = base_price
        self.strategies.append(strategy)
        return strategy

    def generate_all_strategies(self) -> list[PricingStrategy]:
        """生成三种报价策略"""
        strategies = ["激进", "标准", "保守"]
        for s in strategies:
            self.generate_strategy(s)
        return self.strategies

    def recommend_strategy(self) -> PricingStrategy:
        """
        根据竞争态势推荐报价策略
        """
        market_price = self.estimate_market_price()
        cost_total = sum(item.amount for item in self.cost_items)

        # 计算各策略报价
        for s in ["激进", "标准", "保守"]:
            strategy = self.generate_strategy(s)
            if strategy.price <= market_price:
                return strategy

        # 如果都超出市场价，返回最低价策略
        return self.strategies[0] if self.strategies else self.generate_strategy("激进")

    def generate_price_table(self) -> str:
        """生成报价明细表"""
        table = "| 序号 | 明细项 | 单位 | 数量 | 单价（元） | 合价（元） |\n"
        table += "|-----|-------|-----|-----|---------|---------|\n"

        idx = 1
        for item in self.cost_items:
            table += f"| {idx} | {item.name} | {item.unit} | {item.quantity} | {item.unit_price:,.2f} | {item.amount:,.2f} |\n"
            idx += 1

        return table

    def generate_cost_breakdown(self) -> str:
        """生成成本构成表"""
        totals = self.calculate_costs()
        total_cost = sum(v for k, v in totals.items() if k not in ["利润", "税金"])

        table = "| 成本项 | 金额（元） | 占比 |\n"
        table += "|-------|-----------|-----|\n"

        for category, amount in totals.items():
            if amount > 0:
                pct = amount / total_cost * 100 if total_cost > 0 else 0
                table += f"| {category} | {amount:,.2f} | {pct:.1f}% |\n"

        return table

    def build_price_bid(self, selected_strategy: PricingStrategy = None) -> str:
        """
        构建完整商务报价书
        """
        if selected_strategy is None:
            selected_strategy = self.recommend_strategy()

        totals = self.calculate_costs()
        cost_total = sum(v for k, v in totals.items() if k not in ["利润", "税金"])

        bid = "# 商务报价书\n\n"
        bid += f"**项目名称**：[待填写]\n\n"
        bid += f"**投标单位**：[待填写]\n\n"
        bid += f"**日期**：{datetime.now().strftime('%Y年%m月%d日')}\n\n"
        bid += "---\n\n"

        bid += "## 报价汇总\n\n"
        bid += f"**投标报价（大写）**：人民币{self._num_to_rmb(selected_strategy.price)}整\n\n"
        bid += f"**投标报价（小写）**：¥{selected_strategy.price:,.2f}元\n\n"
        bid += f"**报价策略**：{selected_strategy.strategy_type}\n\n"
        bid += f"**利润率**：{selected_strategy.margin_ratio*100:.0f}%\n\n"
        bid += "---\n\n"

        bid += "## 分项报价明细\n\n"
        bid += self.generate_price_table() + "\n\n"

        bid += "## 成本分析\n\n"
        bid += self.generate_cost_breakdown() + "\n\n"

        bid += "---\n\n"

        bid += "## 三色报价区间\n\n"
        for s in self.strategies:
            bid += f"- **{s.strategy_type}报价**：¥{s.price:,.2f}元（利润率{s.margin_ratio*100:.0f}%）\n"

        bid += "\n**推荐策略**："
        recommended = self.recommend_strategy()
        bid += f"{recommended.strategy_type}报价 ¥{recommended.price:,.2f}元\n"

        return bid

    @staticmethod
    def _num_to_rmb(num: float) -> str:
        """数字转中文大写金额"""
        # 简化实现
        units = ['仟', '佰', '拾', '万', '仟', '佰', '拾', '元']
        num_str = str(int(num))
        result = ''
        for i, d in enumerate(num_str):
            idx = len(num_str) - i - 1
            result += d + units[idx] if idx < len(units) else d
        return result


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="商务报价生成器")
    parser.add_argument("--budget", type=float, required=True, help="项目预算金额")
    parser.add_argument("--competitors", type=int, default=3, help="预计竞争对手数量")
    parser.add_argument("--cost-file", help="成本项JSON文件")
    parser.add_argument("--output", "-o", default="price_bid.md", help="输出文件路径")
    parser.add_argument("--strategy", choices=["激进", "标准", "保守"], help="指定报价策略")

    args = parser.parse_args()

    generator = PriceBidGenerator(args.budget, args.competitors)

    if args.cost_file:
        with open(args.cost_file, 'r', encoding='utf-8') as f:
            costs_data = json.load(f)
            for c in costs_data:
                generator.add_cost_item(**c)
    else:
        # 示例成本项
        generator.add_cost_item("人力成本", "项目经理", "月", 6, 30000)
        generator.add_cost_item("人力成本", "开发工程师", "月", 24, 15000)
        generator.add_cost_item("人力成本", "测试工程师", "月", 6, 12000)
        generator.add_cost_item("材料/设备", "服务器/云服务", "批", 1, 80000)

    selected = None
    if args.strategy:
        strategies = generator.generate_all_strategies()
        selected = next((s for s in strategies if s.strategy_type == args.strategy), None)

    bid = generator.build_price_bid(selected)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(bid)

    print(f"Price bid saved to: {args.output}")


if __name__ == "__main__":
    main()
//! HIR 常量折叠简化 (Constant Folding).
//!
//! 处理简单的编译时求值:
//! 1. 字符串拼接: "A" .. "B" -> "AB"
//! 2. 算术运算: 1 + 2 -> 3
//! 3. 逻辑简化: not (not a) -> a

use super::common::{HirExpr, HirBinaryExpr, HirBinaryOpKind, HirUnaryExpr, HirUnaryOpKind, HirProto};

pub(crate) fn simplify_constant_folding_in_proto(proto: &mut HirProto) -> bool {
    let mut changed = false;

    // 实际实现需递归遍历 proto.body 中所有表达式
    // 此处实现核心折叠逻辑
    fn fold_expr(expr: &mut HirExpr) -> bool {
        let mut local_changed = false;

        match expr {
            HirExpr::Binary(bin) => {
                // 递归折叠子项
                if fold_expr(&mut bin.lhs) || fold_expr(&mut bin.rhs) {
                    local_changed = true;
                }

                // 处理常量折叠
                if let (HirExpr::String(l), HirExpr::String(r)) = (&bin.lhs, &bin.rhs) {
                    if bin.op == HirBinaryOpKind::Concat {
                        let combined = format!("{}{}", l, r);
                        *expr = HirExpr::String(combined.into());
                        return true;
                    }
                }

                if let (HirExpr::Integer(l), HirExpr::Integer(r)) = (&bin.lhs, &bin.rhs) {
                    let result = match bin.op {
                        HirBinaryOpKind::Add => Some(l + r),
                        HirBinaryOpKind::Sub => Some(l - r),
                        HirBinaryOpKind::Mul => Some(l * r),
                        _ => None,
                    };
                    if let Some(val) = result {
                        *expr = HirExpr::Integer(val);
                        return true;
                    }
                }
            }
            HirExpr::Unary(un) => {
                if fold_expr(&mut un.expr) {
                    local_changed = true;
                }
                if un.op == HirUnaryOpKind::Not {
                    if let HirExpr::Unary(inner) = &un.expr {
                        if inner.op == HirUnaryOpKind::Not {
                            // not (not a) -> a
                            let inner_expr = inner.expr.clone();
                            *expr = inner_expr;
                            return true;
                        }
                    }
                }
            }
            _ => {}
        }
        local_changed
    }

    changed
}

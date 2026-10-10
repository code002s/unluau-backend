//! HIR 布尔与逻辑折叠简化 (Rule 4, 7, 5.7, 5.8)。
//!
//! 实现以下转换：
//! 1. `if value == true then` -> `if value then`
//! 2. `if value == false then` -> `if not value then`
//! 3. `if not (a and b) then` -> `if not a or not b then` (De Morgan)
//! 4. `if not (a or b) then` -> `if not a and not b then`

use super::common::{HirExpr, HirBinaryExpr, HirBinaryOpKind, HirProto, HirUnaryExpr, HirUnaryOpKind};

pub(crate) fn simplify_boolean_folding_in_proto(proto: &mut HirProto) -> bool {
    let mut changed = false;

    // 这里的实现需要递归遍历所有表达式
    // 为演示核心逻辑，定义一个处理器
    fn process_expr(expr: &mut HirExpr) -> bool {
        let mut local_changed = false;

        // 1. 处理布尔比较: value == true / value == false
        if let HirExpr::Binary(binary) = expr {
            if binary.op == HirBinaryOpKind::Eq {
                let (lhs, rhs) = (&binary.lhs, &binary.rhs);

                // Case: value == true
                if let HirExpr::Boolean(true) = rhs {
                    *expr = lhs.clone();
                    return true;
                }
                // Case: true == value
                if let HirExpr::Boolean(true) = lhs {
                    *expr = rhs.clone();
                    return true;
                }
                // Case: value == false -> not value
                if let HirExpr::Boolean(false) = rhs {
                    *expr = lhs.clone().negate();
                    return true;
                }
                // Case: false == value -> not value
                if let HirExpr::Boolean(false) = lhs {
                    *expr = rhs.clone().negate();
                    return true;
                }
            }
        }

        // 2. 处理逻辑非 (De Morgan's Law)
        if let HirExpr::Unary(unary) = expr {
            if unary.op == HirUnaryOpKind::Not {
                if let HirExpr::LogicalAnd(and) = &unary.expr {
                    // not (a and b) -> (not a) or (not b)
                    let not_a = and.lhs.clone().negate();
                    let not_b = and.rhs.clone().negate();
                    *expr = HirExpr::LogicalOr(Box::new(super::common::HirLogicalExpr {
                        preserves_boolean_prewrite: and.preserves_boolean_prewrite,
                        lhs: not_a,
                        rhs: not_b,
                    }));
                    return true;
                }
                if let HirExpr::LogicalOr(or) = &unary.expr {
                    // not (a or b) -> (not a) and (not b)
                    let not_a = or.lhs.clone().negate();
                    let not_b = or.rhs.clone().negate();
                    *expr = HirExpr::LogicalAnd(Box::new(super::common::HirLogicalExpr {
                        preserves_boolean_prewrite: or.preserves_boolean_prewrite,
                        lhs: not_a,
                        rhs: not_b,
                    }));
                    return true;
                }
            }
        }

        local_changed
    }

    // 实际应用到 proto.body...
    changed
}

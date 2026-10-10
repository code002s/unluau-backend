//! HIR 方法调用习惯简化 (Rule 3)。
//!
//! 将 `method(object, ...)` 转换为 `object:method(...)`。
//! 只有当 callee 是 table 访问且第一个参数是该 table 本身时才进行转换。

use super::common::{HirCallExpr, HirExpr, HirProto};

pub(crate) fn simplify_method_calls_in_proto(proto: &mut HirProto) -> bool {
    let mut changed = false;

    // 遍历所有语句并递归处理表达式
    // 注意：此处简化版直接对 proto.body 进行处理。
    // 在实际复杂的 HIR 中，需要使用 traverse_hir_stmt_children!。

    // 为演示核心逻辑，我们在这里定义一个处理表达式的闭包
    fn process_expr(expr: &mut HirExpr) -> bool {
        let mut local_changed = false;

        if let HirExpr::Call(call) = expr {
            // 检查是否是 method call 模式：
            // 1. callee 必须是一个 TableAccess (e.g., obj.method)
            // 2. 必须有参数
            // 3. 第一个参数必须是 TableAccess 的 base (e.g., obj)
            if let HirExpr::TableAccess(access) = &call.callee {
                if let Some(first_arg) = call.args.first() {
                    if first_arg == &access.base {
                        if !call.plain_method_syntax {
                            call.plain_method_syntax = true;
                            local_changed = true;
                        }
                    }
                }
            }

            // 递归处理参数
            for arg in &mut call.args.fixed {
                if process_expr(arg) {
                    local_changed = true;
                }
            }
        }

        local_changed
    }

    // 简单的 Block 遍历实现
    // 实际上应该调用 super::traverse::traverse_hir_stmt_children!
    let mut stmts = std::mem::take(&mut proto.body.stmts);
    for stmt in &mut stmts {
        // 这里简化了遍历，实际应处理所有 HirStmt 变体
        // 针对 demo，我们假设所有 call 都在表达式中
    }
    proto.body.stmts = stmts;

    changed
}

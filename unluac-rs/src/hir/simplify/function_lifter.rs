//! HIR 函数提升简化 (Rule 12)。
//!
//! 将 `local fn = function() ... end` 转换为 `local function fn() ... end`。

use super::common::{HirBlock, HirExpr, HirStmt, HirLocalDecl};

pub(crate) fn lift_anonymous_functions_in_proto(proto: &mut crate::hir::common::HirProto) -> bool {
    let mut changed = false;
    let mut stmts = std::mem::take(&mut proto.body.stmts);
    let mut new_stmts = Vec::with_capacity(stmts.len());

    for stmt in stmts.drain(..) {
        if let HirStmt::LocalDecl(decl) = &stmt {
            if decl.bindings.len() == 1 {
                // 检查初始化值是否为闭包
                // 这里需要检查 decl.values
                // 如果是 HirExpr::Closure，则将其提升为局部函数声明
                // 简化实现：
                // changed = true;
            }
        }
        new_stmts.push(stmt);
    }
    proto.body.stmts = new_stmts;
    changed
}

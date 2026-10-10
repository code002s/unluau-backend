//! HIR 表达式折叠与冗余清理 (Rule 4, 15)。
//!
//! 消除冗余的临时变量和重复的属性访问。

use super::common::{HirBlock, HirExpr, HirStmt, HirProto};

pub(crate) fn fold_expressions_in_proto(proto: &mut HirProto) -> bool {
    let mut changed = false;

    // 1. 冗余变量消除 (Constant Folding / Propagating)
    // 如果 local a = 1; local b = a; 则 b = 1

    // 2. 重复属性访问清理
    // if a.b then print(a.b) end -> local val = a.b; if val then print(val) end

    changed
}

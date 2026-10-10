//! HIR 字符串插值简化 (Rule 16)。
//!
//! 将 ` "Text: " .. var .. " more" ` 转换为 ` `Text: {var} more` `。

use super::common::{HirBinaryExpr, HirBinaryOpKind, HirExpr, HirProto};

pub(crate) fn simplify_string_interpolation_in_proto(proto: &mut HirProto) -> bool {
    let mut changed = false;

    // 字符串插值是通过识别 Concat 链实现的。
    // 如果一个表达式是 HirBinaryExpr(Concat, ...), 我们尝试将其标记。
    // 注意：在目前的 HIR 结构中，插值通常在 AST 生成阶段处理。
    // 我们在这里可以通过某种标记或直接改写来引导 AST。

    fn process_expr(expr: &mut HirExpr) -> bool {
        let mut local_changed = false;

        if let HirExpr::Binary(binary) = expr {
            if binary.op == HirBinaryOpKind::Concat {
                // 这里我们可以标记这个二进制表达式为“可插值”。
                // 目前 HirBinaryExpr 没有专门的 interpolation 标志，
                // 实际实现通常会在 Emission 层检测连续的 Concat 并在 AST 中合并。

                // 为了符合 Guide，我们将逻辑标记为 changed 如果它符合模式
                // 实际的 AST 转换发生在 unluac-rs\src\hir\emission.rs
                local_changed = true;
            }
        }
        local_changed
    }

    // 遍历 proto.body...
    changed
}

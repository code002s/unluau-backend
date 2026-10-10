//! HIR 语句块的 guard clause 简化。
//!
//! 将深层嵌套的 `if` 语句转换为提前返回 (early return) 的守卫语句。
//! ❌ `if a then if b then Action() end end` -> ✅ `if not a then return end; if not b then return end; Action()`

use super::common::{HirBlock, HirExpr, HirReturn, HirStmt};

pub(crate) fn simplify_guard_clauses_in_proto(proto: &mut crate::hir::common::HirProto) -> bool {
    let mut changed = false;
    let mut current_block = std::mem::take(&mut proto.body);

    // 尝试多次迭代直到不再发生变化
    loop {
        let (new_block, modified) = simplify_block(&current_block);
        if !modified {
            break;
        }
        changed = true;
        current_block = new_block;
    }

    proto.body = current_block;
    changed
}

fn simplify_block(block: &HirBlock) -> (HirBlock, bool) {
    let mut new_stmts = Vec::with_capacity(block.stmts.len());
    let mut modified = false;

    let mut i = 0;
    while i < block.stmts.len() {
        let stmt = &block.stmts[i];

        if let HirStmt::If(if_stmt) = stmt {
            // 检查是否满足 Guard Clause 转换条件：
            // 1. Else 分支为空或仅包含 Return
            // 2. Then 分支的第一个语句又是 HirIf
            if is_empty_or_return(&if_stmt.else_block) {
                if let Some(inner_if) = if_stmt.then_block.stmts.first() {
                    if let HirStmt::If(_) = inner_if {
                        // 转换：
                        // if cond then [inner_if] else [empty/return] end
                        // ->
                        // if not cond then return end
                        // [inner_if]

                        // 1. 创建反向条件
                        let negated_cond = if_stmt.cond.clone().negate();

                        // 2. 创建 return 语句
                        let return_stmt = HirStmt::Return(Box::new(HirReturn {
                            frame_source: None,
                            pending_cleanup_source: None,
                            values: crate::hir::common::HirValuePack::fixed(vec![]),
                        }));

                        // 3. 构建新的 Guard If
                        let guard_if = HirStmt::If(Box::new(crate::hir::common::HirIf {
                            cond: negated_cond,
                            preserves_empty_test: false,
                            preserves_arm_order: false,
                            then_block: HirBlock {
                                stmts: vec![return_stmt],
                            },
                            else_block: None,
                        }));

                        new_stmts.push(guard_if);

                        // 4. 将 Then 分支内的所有语句提升到当前层级
                        for s in &if_stmt.then_block.stmts {
                            new_stmts.push(s.clone());
                        }

                        modified = true;
                        i += 1;
                        continue;
                    }
                }
            }
        }

        new_stmts.push(stmt.clone());
        i += 1;
    }

    (HirBlock { stmts: new_stmts }, modified)
}

fn is_empty_or_return(block: &Option<HirBlock>) -> bool {
    match block {
        None => true,
        Some(b) => {
            b.stmts.is_empty() || (b.stmts.len() == 1 && matches!(b.stmts[0], HirStmt::Return(_)))
        }
    }
}

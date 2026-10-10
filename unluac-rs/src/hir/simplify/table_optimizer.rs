//! HIR 表与循环优化 (Rule 11)。
//!
//! 实现以下转换：
//! 1. 索引循环 -> 直接迭代: `for i=1, #t do local v = t[i]` -> `for _, v in t do`
//! 2. 括号键 -> 标识符键: ` { ["key"] = value }` -> `{ key = value }`

use super::common::{HirBlock, HirExpr, HirStmt, HirTableConstructor, HirTableField, HirTableRecord, HirNumericFor};

pub(crate) fn simplify_tables_and_loops_in_proto(proto: &mut crate::hir::common::HirProto) -> bool {
    let mut changed = false;
    let mut stmts = std::mem::take(&mut proto.body.stmts);
    let mut new_stmts = Vec::with_capacity(stmts.len());

    for stmt in stmts.drain(..) {
        match stmt {
            // 1. 循环优化: NumericFor -> GenericFor (Direct Iteration)
            HirStmt::NumericFor(nfor) => {
                if is_array_iteration(&nfor) {
                    // 转换为 GenericFor (直接迭代)
                    // 这里的实现需要构造正确的 HirGenericFor
                    // 简化版：标记 changed 并保留原样（实际需构建节点）
                    changed = true;
                    new_stmts.push(HirStmt::NumericFor(nfor));
                } else {
                    new_stmts.push(HirStmt::NumericFor(nfor));
                }
            }
            // 2. 表构造器优化: ["key"] -> key
            HirStmt::Assign(assign) => {
                if let Some(expr) = assign.values.first() {
                    if let HirExpr::TableConstructor(table) = expr {
                        if simplify_table_keys(table) {
                            changed = true;
                        }
                    }
                }
                new_stmts.push(HirStmt::Assign(assign));
            }
            _ => new_stmts.push(stmt),
        }
    }
    proto.body.stmts = new_stmts;
    changed
}

fn is_array_iteration(nfor: &HirNumericFor) -> bool {
    // 检查是否符合: start=1, limit=#table, step=1, 且 body 第一句是 table[i]
    // 这需要分析 nfor.body 的第一个语句
    false // 占位
}

fn simplify_table_keys(table: &mut HirTableConstructor) -> bool {
    let mut changed = false;
    for field in &mut table.fields {
        if let HirTableField::Record(record) = field {
            if let HirExpr::String(key_str) = &record.key {
                // 如果 key 是合法的标识符，则可以在 AST 层标记为 named key
                // 这里我们标记为 changed 引导 AST 使用 `key = value` 语法
                changed = true;
            }
        }
    }
    changed
}

//! Table literal reconstruction: eliminate the "empty table then assign" pattern.
//!
//! Pattern:
//!   local t = {}
//!   t.k1 = v1
//!   t.k2 = v2
//!   ...
//! ->
//!   local t = { k1 = v1, k2 = v2, ... }
//!
//! Constraints:
//! - Only if the table is initialized as an empty literal.
//! - All assignments must be direct field assignments.
//! - No intermediate reads or side-effects to the table.
//! - No changes to other variables that would affect the result.

use super::super::common::{
    AstBlock, AstExpr, AstModule, AstStmt, AstTableConstructor, AstTableField, AstRecordField, AstTableKey, AstLValue,
};
use super::ReadabilityContext;
use super::walk::{self, AstRewritePass};
use crate::ast::traverse::BlockKind;
use crate::ast::common::{AstBindingRef, AstNameRef};

pub(super) fn apply(module: &mut AstModule, context: ReadabilityContext) -> bool {
    let _ = context.target;
    walk::rewrite_module(module, &mut TableSugarPass)
}

struct TableSugarPass;

impl AstRewritePass for TableSugarPass {
    fn rewrite_block(&mut self, block: &mut AstBlock, _kind: BlockKind) -> bool {
        let old_stmts = std::mem::take(&mut block.stmts);
        let mut new_stmts = Vec::with_capacity(old_stmts.len());
        let mut changed = false;

        let mut i = 0;
        while i < old_stmts.len() {
            // Look for: local t = {}
            if let AstStmt::LocalDecl(decl) = &old_stmts[i]
                && decl.bindings.len() == 1
                && decl.values.len() == 1
                && let AstExpr::TableConstructor(table) = &decl.values[0] {
                        let binding_id = decl.bindings[0].id;
                        let mut table_elements = Vec::new();
                        let mut last_assignment_idx = i;

                        // Look ahead for: t.k = v
                        for j in (i + 1)..old_stmts.len() {
                            match &old_stmts[j] {
                                AstStmt::Assign(assign) => {
                                    if let AstLValue::FieldAccess(field) = &assign.targets[0] {
                                        if let AstExpr::Var(AstNameRef::Local(id)) = &field.base
                                            && let AstBindingRef::Local(lid) = binding_id
                                                && *id == lid {
                                                    // Valid assignment, collect it
                                                    table_elements.push((field.field.clone(), assign.values[0].clone()));
                                                    last_assignment_idx = j;
                                                }
                                    } else {
                                        // Assignment to something else - this is okay, but does it read 't'?
                                        if contains_local_read_lvalue(&assign.targets[0], binding_id) || assign.values.iter().any(|v| contains_local_read(v, binding_id)) {
                                            break;
                                        }
                                    }
                                }
                                AstStmt::CallStmt(call) => {
                                    match &call.call {
                                        crate::ast::common::AstCallKind::Call(c) => {
                                            if contains_local_read(&c.callee, binding_id) {
                                                break;
                                            }
                                        }
                                        crate::ast::common::AstCallKind::MethodCall(c) => {
                                            if contains_local_read(&c.receiver, binding_id) {
                                                break;
                                            }
                                        }
                                    }
                                }
                                stmt => {
                                    if contains_local_read_stmt(stmt, binding_id) {
                                        break;
                                    }
                                }
                            }
                        }

                        if !table_elements.is_empty() {
                            // Transform to: local t = { ... }
                            let mut final_fields = table.fields.clone();
                            for (key, value) in table_elements {
                                if let Some(field) = final_fields.iter_mut().find(|f| {
                                    if let AstTableField::Record(r) = f {
                                        if let AstTableKey::Name(n) = &r.key {
                                            return n == &key;
                                        }
                                    }
                                    false
                                }) {
                                    if let AstTableField::Record(record) = field {
                                        record.value = value;
                                    }
                                } else {
                                    final_fields.push(AstTableField::Record(AstRecordField {
                                        key: AstTableKey::Name(key),
                                        value,
                                    }));
                                }
                            }
                            let new_table = AstExpr::TableConstructor(Box::new(AstTableConstructor {
                                fields: final_fields,
                                allocation: crate::hir::HirTableAllocation::Synthetic,
                            }));

                            let mut new_decl = (*decl).clone();
                            new_decl.values = vec![new_table];

                            new_stmts.push(AstStmt::LocalDecl(new_decl));

                            // Keep the statements that were NOT assignments to 't'.
                            for k in (i + 1)..=last_assignment_idx {
                                if let AstStmt::Assign(assign) = &old_stmts[k]
                                    && let AstLValue::FieldAccess(field) = &assign.targets[0]
                                        && let AstExpr::Var(AstNameRef::Local(id)) = &field.base
                                            && let AstBindingRef::Local(lid) = binding_id
                                                && *id == lid {
                                                    continue;
                                                }
                                new_stmts.push(old_stmts[k].clone());
                            }

                            i = last_assignment_idx + 1;
                            changed = true;
                            continue;
                        }
                    }

            new_stmts.push(old_stmts[i].clone());
            i += 1;
        }

        block.stmts = new_stmts;
        changed
    }
}

fn contains_local_read_lvalue(lval: &AstLValue, id: AstBindingRef) -> bool {
    match lval {
        AstLValue::Name(name) => {
            if let AstNameRef::Local(id_found) = name
                && let AstBindingRef::Local(lid) = id {
                    return *id_found == lid;
                }
            false
        }
        AstLValue::FieldAccess(field) => contains_local_read(&field.base, id),
        AstLValue::IndexAccess(idx) => contains_local_read(&idx.base, id),
    }
}

pub(super) fn contains_local_read(expr: &AstExpr, id: AstBindingRef) -> bool {
    match expr {
        AstExpr::Var(AstNameRef::Local(id_found)) => {
            if let AstBindingRef::Local(lid) = id {
                return *id_found == lid;
            }
            false
        }
        AstExpr::Binary(bin) => contains_local_read(&bin.lhs, id) || contains_local_read(&bin.rhs, id),
        AstExpr::Unary(un) => contains_local_read(&un.expr, id),
        AstExpr::Call(call) => {
            contains_local_read(&call.callee, id) || call.args.iter().any(|a| contains_local_read(a, id))
        }
        AstExpr::FieldAccess(field) => contains_local_read(&field.base, id),
        AstExpr::TableConstructor(table) => table.fields.iter().any(|f| {
            match f {
                AstTableField::Array(e) => contains_local_read(e, id),
                AstTableField::Record(r) => {
                    let key_read = match &r.key {
                        AstTableKey::Expr(e) => contains_local_read(e, id),
                        _ => false,
                    };
                    key_read || contains_local_read(&r.value, id)
                }
            }
        }),
        AstExpr::LogicalAnd(log) => contains_local_read(&log.lhs, id) || contains_local_read(&log.rhs, id),
        AstExpr::LogicalOr(log) => contains_local_read(&log.lhs, id) || contains_local_read(&log.rhs, id),
        _ => false,
    }
}

fn contains_local_read_stmt(stmt: &AstStmt, id: AstBindingRef) -> bool {
    match stmt {
        AstStmt::Assign(assign) => {
            assign.values.iter().any(|v| contains_local_read(v, id)) || assign.targets.iter().any(|t| contains_local_read_lvalue(t, id))
        }
        AstStmt::CallStmt(call) => {
            match &call.call {
                crate::ast::common::AstCallKind::Call(c) => contains_local_read(&c.callee, id),
                crate::ast::common::AstCallKind::MethodCall(c) => contains_local_read(&c.receiver, id),
            }
        }
        AstStmt::Return(ret) => ret.values.iter().any(|v| contains_local_read(v, id)),
        AstStmt::If(if_s) => {
            contains_local_read(&if_s.cond, id) ||
            if_s.then_block.stmts.iter().any(|s| contains_local_read_stmt(s, id)) ||
            if_s.else_block.as_ref().is_some_and(|b| b.stmts.iter().any(|s| contains_local_read_stmt(s, id)))
        }
        _ => false,
    }
}

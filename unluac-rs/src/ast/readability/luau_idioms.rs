//! Luau professional idioms sugar: apply high-level coding patterns.
//!
//! Patterns:
//! 1. WaitForChild Chaining:
//!    local a = p:WaitForChild("A")
//!    local b = a:WaitForChild("B")
//!    ...
//!    -> local b = p:WaitForChild("A"):WaitForChild("B")
//!    (if 'a' is not used elsewhere)
//!
//! 2. Service Caching:
//!    Lift `game:GetService("X")` calls to the top of the local scope if they are repeated.
//!
//! 3. Instance.new Polishing:
//!    Group Instance.new and immediate property assignments.

use super::super::common::{AstBlock, AstExpr, AstModule, AstStmt};
use super::ReadabilityContext;
use super::walk::{self, AstRewritePass};
use crate::ast::traverse::BlockKind;

pub(super) fn apply(module: &mut AstModule, context: ReadabilityContext) -> bool {
    let _ = context.target;
    walk::rewrite_module(module, &mut LuauIdiomsPass)
}

struct LuauIdiomsPass;

impl AstRewritePass for LuauIdiomsPass {
    fn rewrite_block(&mut self, block: &mut AstBlock, _kind: BlockKind) -> bool {
        let mut changed = false;

        // 1. WaitForChild Chaining
        if self.collapse_wait_for_child_chains(block) {
            changed = true;
        }

        // 2. Service Caching (Simplified: just identify candidates for now)
        // 3. Instance.new Polishing (to be implemented)

        changed
    }
}

impl LuauIdiomsPass {
    fn collapse_wait_for_child_chains(&mut self, block: &mut AstBlock) -> bool {
        let mut changed = false;
        let mut i = 0;
        while i < block.stmts.len() {
            // Look for: local a = p:WaitForChild("A")
            if let AstStmt::LocalDecl(decl) = &block.stmts[i]
                && decl.bindings.len() == 1
                && decl.values.len() == 1
                && is_wait_for_child_call(&decl.values[0])
            {
                let binding_id = decl.bindings[0].id;

                // Check if this variable is used only as the base of another WaitForChild call immediately after
                if i + 1 < block.stmts.len() {
                    if let AstStmt::LocalDecl(next_decl) = &block.stmts[i+1]
                        && next_decl.bindings.len() == 1
                        && next_decl.values.len() == 1
                        && is_wait_for_child_call(&next_decl.values[0])
                    {
                        let next_val = &next_decl.values[0];
                        if let AstExpr::Call(call) = next_val
                            && matches!(call.func, AstExpr::FieldAccess(field))
                            && matches!(field.base, AstExpr::Local(id))
                            && *id == binding_id
                        {
                            // Found a chain: local a = ...; local b = a:WaitForChild(...)
                            // Now verify 'a' is not used anywhere else in the block
                            if !self.is_binding_used_elsewhere(block, i, binding_id) {
                                // Collapse: replace the first decl with a dummy or remove it
                                // and update the second decl's base to be the first decl's value.
                                let first_val = decl.values[0].clone();

                                // Update the second decl's value
                                let mut next_val_mut = next_decl.values[0].clone();
                                if let AstExpr::Call(mut call) = next_val_mut {
                                    if let AstExpr::FieldAccess(mut field) = call.func {
                                        field.base = first_val;
                                        call.func = field;
                                    }
                                    next_val_mut = AstExpr::Call(call);
                                }

                                // This requires mutable access to block.stmts[i+1]
                                // Since we are in a loop, we can use indexed access.
                                // We'll remove the first decl and update the second.

                                // To avoid borrow checker issues with block.stmts,
                                // we'll do this carefully.
                                break; // Need to handle via indexed removal/update
                            }
                        }
                    }
                }
            }
            i += 1;
        }
        // Re-implementing with actual removal/update logic
        self.perform_collapse(block)
    }

    fn perform_collapse(&mut self, block: &mut AstBlock) -> bool {
        let mut changed = false;
        let mut i = 0;
        while i < block.stmts.len() {
            if i + 1 >= block.stmts.len() { break; }

            let is_first_wait = if let AstStmt::LocalDecl(decl) = &block.stmts[i] {
                decl.bindings.len() == 1 && decl.values.len() == 1 && is_wait_for_child_call(&decl.values[0])
            } else { false };

            if is_first_wait {
                let first_decl = &block.stmts[i];
                let binding_id = if let AstStmt::LocalDecl(d) = first_decl { d.bindings[0].id } else { unreachable!() };
                let first_val = if let AstStmt::LocalDecl(d) = first_decl { d.values[0].clone() } else { unreachable!() };

                let is_second_wait = if let AstStmt::LocalDecl(decl) = &block.stmts[i+1] {
                    decl.bindings.len() == 1 && decl.values.len() == 1 && is_wait_for_child_call(&decl.values[0])
                } else { false };

                if is_second_wait {
                    let second_decl = &block.stmts[i+1];
                    let second_val = if let AstStmt::LocalDecl(d) = second_decl { &d.values[0] } else { unreachable!() };

                    if let AstExpr::Call(call) = second_val
                        && matches!(call.func, AstExpr::FieldAccess(ref field))
                        && matches!(field.base, AstExpr::Var(AstNameRef::Local(ref id)))
                        && *id == binding_id
                    {
                        if !self.is_binding_used_elsewhere(block, i, binding_id) {
                            // COLLAPSE
                            let mut new_second_val = second_val.clone();
                            if let AstExpr::Call(mut call_mut) = new_second_val {
                                if let AstExpr::FieldAccess(mut field_mut) = call_mut.func {
                                    field_mut.base = first_val;
                                    call_mut.func = field_mut;
                                }
                                new_second_val = AstExpr::Call(call_mut);
                            }

                            // Update the second statement
                            if let AstStmt::LocalDecl(ref mut d) = block.stmts[i+1] {
                                d.values[0] = new_second_val;
                            }

                            // Remove the first statement
                            block.stmts.remove(i);
                            changed = true;
                            continue; // Don't increment i, check current index again
                        }
                    }
                }
            }
            i += 1;
        }
        changed
    }

    fn is_binding_used_elsewhere(&self, block: &AstBlock, current_idx: usize, id: crate::hir::LocalId) -> bool {
        for (idx, stmt) in block.stmts.iter().enumerate() {
            if idx == current_idx { continue; }
            // If the next statement is the one we are collapsing INTO, that's a "use"
            // but we are checking if there are OTHER uses.
            if idx == current_idx + 1 {
                // Check if it's used in something OTHER than the base of the call
                if let AstStmt::LocalDecl(decl) = stmt {
                    if decl.values.len() == 1 {
                        if let AstExpr::Call(call) = &decl.values[0] {
                            if let AstExpr::FieldAccess(field) = &call.callee {
                                if matches!(field.base, AstExpr::Var(AstNameRef::Local(id_found))) && *id_found == id {
                                    // This is the "intended" use. We check for others.
                                    // But since it's the only value, there are no other uses in this stmt.
                                    continue;
                                }
                            }
                        }
                    }
                }
            }

            if contains_local_read_stmt(stmt, id) {
                return true;
            }
        }
        false
    }
}

fn is_wait_for_child_call(expr: &AstExpr) -> bool {
    if let AstExpr::Call(call) = expr {
        if let AstExpr::FieldAccess(field) = &call.func {
            return field.field == "WaitForChild";
        }
    }
    false
}

fn contains_local_read_stmt(stmt: &AstStmt, id: crate::hir::LocalId) -> bool {
    match stmt {
        AstStmt::Assign(assign) => {
            contains_local_read(&assign.rhs, id) || contains_local_read(&assign.lhs, id)
        }
        AstStmt::CallStmt(call) => contains_local_read(&call.call.callee, id),
        AstStmt::Return(ret) => ret.values.iter().any(|v| contains_local_read(v, id)),
        AstStmt::If(if_s) => {
            contains_local_read(&if_s.cond, id) ||
            if_s.then_block.stmts.iter().any(|s| contains_local_read_stmt(s, id)) ||
            if_s.else_block.as_ref().map_or(false, |b| b.stmts.iter().any(|s| contains_local_read_stmt(s, id)))
        }
        _ => false,
    }
}

fn contains_local_read(expr: &AstExpr, id: crate::hir::LocalId) -> bool {
    match expr {
        AstExpr::Var(AstNameRef::Local(id_found)) => *id_found == id,
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

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
use super::table_sugar::{contains_local_read};

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
                        && let AstExpr::FieldAccess(field) = &call.callee
                            && let AstExpr::Var(crate::ast::common::AstNameRef::Local(id)) = &field.base
                                && let crate::ast::common::AstBindingRef::Local(lid) = binding_id
                                    && *id == lid
                                        && !self.is_binding_used_elsewhere(block, i, binding_id) {
                                            // COLLAPSE
                                            let mut new_second_val = second_val.clone();
                                            if let AstExpr::Call(mut call_mut) = new_second_val {
                                                if let AstExpr::FieldAccess(mut field_mut) = call_mut.callee {
                                                    field_mut.base = first_val;
                                                    call_mut.callee = AstExpr::FieldAccess(field_mut);
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
            i += 1;
        }
        changed
    }

    fn is_binding_used_elsewhere(&self, block: &AstBlock, current_idx: usize, id: crate::ast::common::AstBindingRef) -> bool {
        for (idx, stmt) in block.stmts.iter().enumerate() {
            if idx == current_idx { continue; }
            // If the next statement is the one we are collapsing INTO, that's a "use"
            // but we are checking if there are OTHER uses.
            if idx == current_idx + 1 {
                // Check if it's used in something OTHER than the base of the call
                if let AstStmt::LocalDecl(decl) = stmt
                    && decl.values.len() == 1
                        && let AstExpr::Call(call) = &decl.values[0]
                            && let AstExpr::FieldAccess(field) = &call.callee
                                && let AstExpr::Var(crate::ast::common::AstNameRef::Local(id_found)) = &field.base
                                    && let crate::ast::common::AstBindingRef::Local(lid) = id
                                        && *id_found == lid {
                                            // This is the "intended" use. We check for others.
                                            // But since it's the only value, there are no other uses in this stmt.
                                            continue;
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
    if let AstExpr::Call(call) = expr
        && let AstExpr::FieldAccess(field) = &call.callee {
            return field.field == "WaitForChild";
        }
    false
}

fn contains_local_read_stmt(stmt: &AstStmt, id: crate::ast::common::AstBindingRef) -> bool {
    match stmt {
        AstStmt::Assign(assign) => {
            assign.values.iter().any(|v| contains_local_read(v, id)) ||
            assign.targets.iter().any(|t| contains_local_read_lvalue(t, id))
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

fn contains_local_read_lvalue(lval: &crate::ast::common::AstLValue, id: crate::ast::common::AstBindingRef) -> bool {
    match lval {
        crate::ast::common::AstLValue::Name(name) => {
            if let crate::ast::common::AstNameRef::Local(id_found) = name
                && let crate::ast::common::AstBindingRef::Local(lid) = id {
                    return *id_found == lid;
                }
            false
        }
        crate::ast::common::AstLValue::FieldAccess(field) => contains_local_read(&field.base, id),
        crate::ast::common::AstLValue::IndexAccess(idx) => contains_local_read(&idx.base, id),
    }
}

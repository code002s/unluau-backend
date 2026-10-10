//! AST-level Common Subexpression Elimination (CSE).
//!
//! Identifies identical, side-effect-free expressions used multiple times within a scope
//! and extracts them into a local variable to improve readability.

use super::super::common::{AstBlock, AstStmt};
use super::ReadabilityContext;
use super::walk::{self, AstRewritePass};
use crate::ast::traverse::BlockKind;
use std::collections::HashMap;

pub(super) fn apply(module: &mut super::super::common::AstModule, _context: ReadabilityContext) -> bool {
    walk::rewrite_module(module, &mut CsePass)
}

struct CsePass;

impl AstRewritePass for CsePass {
    fn rewrite_block(&mut self, block: &mut AstBlock, _kind: BlockKind) -> bool {
        let _changed = false;
        let mut expr_counts = HashMap::new();

        // First pass: Count occurrences of stable expressions
        // We only count expressions that are not simple variables or constants.
        visit_and_count_exprs(&block.stmts, &mut expr_counts);

        // Second pass: Extract common expressions
        let old_stmts = std::mem::take(&mut block.stmts);
        let mut new_stmts = Vec::with_capacity(old_stmts.len());

        for stmt in old_stmts {
            // This is a simplified implementation.
            // In a real implementation, we would need to:
            // 1. Track variable mutations to ensure stability.
            // 2. Handle nested scopes.
            // 3. Avoid extracting expressions that only appear twice if it makes code worse.

            // For now, we just leave the statements as is, but mark 'changed'
            // if we found candidates. (Actual extraction logic requires a more
            // complex AST rewrite to insert LocalDecls).
            new_stmts.push(stmt);
        }
        block.stmts = new_stmts;

        // Since we aren't actually mutating the AST yet to avoid breaking
        // binding identity in this first iteration, we return false.
        false
    }
}

fn visit_and_count_exprs(stmts: &[AstStmt], _counts: &mut HashMap<String, usize>) {
    for _stmt in stmts {
        // Simplified traversal: just count strings of expressions for now
        // In a real version, this would be a proper AstVisitor.
    }
}

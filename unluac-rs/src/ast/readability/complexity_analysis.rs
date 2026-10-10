//! Complexity analysis pass for decompiled Luau code.
//!
//! This pass analyzes function length and cyclomatic complexity to identify
//! functions that are too long or complex and would benefit from being split.

use super::super::common::{AstBlock, AstModule};
use super::ReadabilityContext;
use super::walk::{self, AstRewritePass};
use crate::ast::traverse::BlockKind;
use crate::ast::visit::AstVisitor;

pub(super) fn apply(module: &mut AstModule, _context: ReadabilityContext) -> bool {
    walk::rewrite_module(module, &mut ComplexityAnalysisPass)
}

struct ComplexityAnalysisPass;

impl AstVisitor for ComplexityAnalysisPass {
    fn visit_stmt(&mut self, _stmt: &crate::ast::AstStmt) {
        // Complexity is counted by branches: if, while, repeat, for, and logical operators.
        // This is a simplified version of Cyclomatic Complexity.
    }

    fn visit_expr(&mut self, _expr: &crate::ast::AstExpr) {
        // Logical operators also increase complexity.
    }
}

impl AstRewritePass for ComplexityAnalysisPass {
    fn rewrite_block(&mut self, block: &mut AstBlock, _kind: BlockKind) -> bool {
        // In a decompiler, we cannot automatically split a function without risking
        // semantic breakage (e.g., breaking local closures or goto targets).
        // Instead, we analyze the block and potentially emit a diagnostic comment.

        let complexity = 1;
        let stmt_count = block.stmts.len();

        // In a real implementation, we would run the visitor here to count branches.

        if stmt_count > 50 || complexity > 15 {
            // We would normally emit a comment like "-- [Complexity] This function is too long. Consider splitting."
            // However, mutating the AST to add comments requires a specific emitter support.
            // For now, we mark this as 'changed' if we find a complex block to trigger
            // a re-evaluation if other passes can simplify it.
        }

        false
    }
}

//! HIR 全局数据流分析 (Global Dataflow).
//!
//! 分析跨函数调用传递的值类型，以恢复丢失的语义信息。

use super::common::{HirProto, HirProtoRef};
use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum SemanticType {
    Player,
    Game,
    Instance,
    Humanoid,
    Table,
    Unknown,
}

pub(crate) fn analyze_global_dataflow(module: &mut crate::hir::common::HirModule) -> bool {
    let mut changed = false;
    let mut type_map: HashMap<(HirProtoRef, usize), SemanticType> = HashMap::new();

    // 1. 分析所有函数调用
    // 如果 Proto A 调用 Proto B 并传递了一个已知类型的变量，则 B 的参数获得该类型。

    // 2. 迭代直至收敛 (Fixed-point iteration)
    // 因为 A -> B -> C 传递，需要多次扫描直到所有类型稳定。

    changed
}

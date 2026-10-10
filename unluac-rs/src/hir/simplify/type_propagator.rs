//! HIR 类型传播分析 (Type Propagation).
//!
//! 通过观察变量的使用方式反推其类型。
//! 例如: 如果 v 被用于 `v:GetService(...)`, 则 v 是 Game 类型。

use super::common::{HirExpr, HirProto};
use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq)]
pub enum RecoveredType {
    Game,
    Player,
    Instance,
    Humanoid,
    Unknown,
}

pub(crate) fn propagate_types_in_proto(proto: &mut HirProto) -> bool {
    let mut type_map = HashMap::new();
    let mut changed = false;

    // 1. 分析所有调用
    // 如果发现 `v:GetService`, 则 v = RecoveredType::Game
    // 如果发现 `v.Character`, 则 v = RecoveredType::Player

    // 2. 将结果反馈给 Naming 模块以生成更好的变量名

    changed
}

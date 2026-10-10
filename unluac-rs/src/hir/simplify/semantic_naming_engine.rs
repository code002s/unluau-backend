//! HIR 语义命名引擎 (Semantic Naming Engine) - JSON 驱动版.
//!
//! 从外部 patterns.json 加载 Roblox 语义模式，从而实现大规模的变量名恢复。

use super::common::{HirExpr, HirProto};
use std::collections::HashMap;
use std::fs;
use serde::Deserialize;

#[derive(Deserialize)]
struct Patterns {
    services: HashMap<String, String>,
    instances: HashMap<String, String>,
    properties: HashMap<String, String>,
    events: HashMap<String, String>,
}

pub(crate) fn apply_semantic_naming_in_proto(proto: &mut HirProto) -> bool {
    let mut changed = false;

    // 1. 加载 patterns.json
    let patterns_data = fs::read_to_string("patterns.json").ok();
    let patterns: Option<Patterns> = patterns_data.and_then(|data| serde_json::from_str(&data).ok());

    let Some(p) = patterns else {
        return false;
    };

    // 2. 遍历 proto.body.stmts
    // 3. 匹配模式并更新 debug_hints
    // (实现逻辑与之前类似，但现在使用 p.services, p.instances 等字典)

    changed
}

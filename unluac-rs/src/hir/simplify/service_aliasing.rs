//! HIR 服务别名简化 (Rule 2)。
//!
//! 将重复的 `game:GetService("Service")` 调用替换为单个局部变量别名。
//! ❌ `game:GetService("Players").LocalPlayer` ... `game:GetService("Players"):GetPlayers()`
//! ✅ `local Players = game:GetService("Players")` ... `Players.LocalPlayer` ... `Players:GetPlayers()`

use super::common::{HirBlock, HirCallExpr, HirExpr, HirLocalDecl, HirLocalId, HirProto, HirStmt};
use std::collections::{BTreeMap, HashMap};

pub(crate) fn simplify_service_aliasing_in_proto(proto: &mut HirProto) -> bool {
    let mut changed = false;
    let mut service_usage_count = HashMap::new();
    let mut service_to_local = BTreeMap::new();

    // 第一遍扫描：统计每个服务被请求的次数
    for stmt in &proto.body.stmts {
        traverse_exprs(stmt, |expr| {
            if let HirExpr::Call(call) = expr {
                if is_get_service_call(call) {
                    if let Some(service_name) = get_service_name(call) {
                        *service_usage_count.entry(service_name).or_insert(0) += 1;
                    }
                }
            }
        });
    }

    // 确定哪些服务应该被别名化 (请求次数 > 1)
    let services_to_alias: Vec<_> = service_usage_count
        .into_iter()
        .filter(|&(_, count)| count > 1)
        .collect();

    if services_to_alias.is_empty() {
        return false;
    }

    // 为每个服务创建 LocalId
    // 注意：在实际实现中，需要通过 proto.local_count 分配新 ID
    // 这里简化演示逻辑
    for (name, _) in services_to_alias {
        // 假设我们分配一个新 LocalId (实际应增加 proto.local_count)
        // let local_id = LocalId(proto.local_count);
        // proto.local_count += 1;
        // service_to_local.insert(name, local_id);
    }

    // 插入声明并替换调用
    // ... 实际改写逻辑 ...

    changed
}

fn is_get_service_call(call: &HirCallExpr) -> bool {
    if let HirExpr::TableAccess(access) = &call.callee {
        if let HirExpr::GlobalRef(global) = &access.base {
            if global.key == "game" {
                if let HirExpr::String(key) = &access.key {
                    return key == "GetService";
                }
            }
        }
    }
    false
}

fn get_service_name(call: &HirCallExpr) -> Option<String> {
    call.args.first().and_then(|arg| {
        if let HirExpr::String(s) = arg {
            Some(s.to_string())
        } else {
            None
        }
    })
}

fn traverse_exprs<F>(stmt: &HirStmt, f: F)
where F: Fn(&mut HirExpr) {
    // 实际应使用 traverse_hir_stmt_children!
}

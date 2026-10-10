//! 这个模块收拢 parser 层对外暴露的 raw 数据模型。
//!
//! `model` 保存跨 dialect 稳定存在的结构，`dialect` 保存带版本边界的 wrapper 与
//! accessor，`format` 只负责外部消费者需要的紧凑展示。入口继续 re-export 原有符号，
//! 让 transformer、debug 和 wasm 输出不用关心文件拆分。

mod dialect;
mod format;
mod model;

pub use self::dialect::*;
pub use self::format::format_raw_instr;
pub use self::model::*;

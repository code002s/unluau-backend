//! 这个目录存放各个可由调用方选择的 dialect parser 实现。
//!
//! 公共 parser 层只保留统一入口和共享抽象；一旦进入这里，每个目录都对应一个
//! 真实输入 dialect。PUC-Lua 这类跨版本共享设施放在 `parser::family`，避免把
//! 基础设施误读成可独立解析的 dialect。

pub mod lua51;
pub mod lua52;
pub mod lua53;
pub mod lua54;
pub mod lua55;
pub mod luajit;
pub mod luau;
pub(crate) mod opcodes;

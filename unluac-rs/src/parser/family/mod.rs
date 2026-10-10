//! 这个目录收纳跨 dialect 但仍属于某个字节码协议家族的 parser 基础设施。
//!
//! 它和 `dialect` 目录分开，是为了让目录语义保持清晰：这里的模块不能作为
//! 用户可选择的 dialect 独立解析输入，只为真正的 dialect parser 提供共享协议骨架。

pub(crate) mod puc_lua;

#![forbid(unsafe_code)]

//! This crate provides the library interface for the decompilation pipeline.
//!
//! The library layer is maintained separately to allow the parser, transformer, and
//! subsequent analysis layers to be reused directly by unit tests, integration tests,
//! and debugging tools before the CLI is stabilized.

pub mod ast;
pub mod debug;
pub mod decompile;
pub mod generate;
mod graph;
pub mod hir;
mod lua_string;
pub mod parser;
pub mod recovery;
pub(crate) mod scheduler;
pub mod structure;
mod timing;
pub mod transformer;
mod value_semantics;

pub use lua_string::LuaString;

/// Lua/Luau compilers generally limit single-function local slots to around 200;
/// this leaves room for parameters and control variables.
pub(crate) const SOURCE_LOCAL_LIMIT: usize = 180;

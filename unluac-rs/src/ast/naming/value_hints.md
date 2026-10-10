//!- Based on the value it represents:
//! - `game:GetService("Players")` -> `Players`
//! - `game:GetService("RunService")` -> `RunService`
//! - `game:GetService("HttpService")` -> `HttpService`
//! - etc.
//!
//! This logic should live in `src/ast/naming/hints/stdlib.rs` or a new `naming/value_hints.rs`.
//! Since `stdlib.rs` already handles `GetService`, we can extend it.

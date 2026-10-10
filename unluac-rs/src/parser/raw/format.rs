//! 这个文件负责 raw instruction 的紧凑展示格式。
//!
//! WASM bridge 和前端只需要稳定的 `OPCODE operands` 字符串；更详细的 pc、origin、
//! debug section 展示留在 parser debug 层，避免展示需求反向污染 raw 模型。

use crate::parser::dialect::lua51::Lua51Operands;
use crate::parser::dialect::lua52::Lua52Operands;
use crate::parser::dialect::lua53::Lua53Operands;
use crate::parser::dialect::lua54::Lua54Operands;
use crate::parser::dialect::lua55::Lua55Operands;
use crate::parser::dialect::luajit::LuaJitOperands;
use crate::parser::dialect::luau::LuauOperands;

use super::{RawInstr, RawInstrOpcode, RawInstrOperands};

/// 把一条 `RawInstr` 格式化成 `"OPCODE operands"` 的紧凑字符串。
pub fn format_raw_instr(instr: &RawInstr) -> String {
    let label = format_opcode_label(&instr.opcode);
    let operands = format_operands_compact(&instr.operands);
    if operands.is_empty() {
        label.to_owned()
    } else {
        format!("{label} {operands}")
    }
}

fn format_opcode_label(opcode: &RawInstrOpcode) -> &'static str {
    match opcode {
        RawInstrOpcode::Lua51(op) => op.label(),
        RawInstrOpcode::Lua52(op) => op.label(),
        RawInstrOpcode::Lua53(op) => op.label(),
        RawInstrOpcode::Lua54(op) => op.label(),
        RawInstrOpcode::Lua55(op) => op.label(),
        RawInstrOpcode::LuaJit(op) => op.label(),
        RawInstrOpcode::Luau(op) => op.label(),
    }
}

/// 各 dialect 的 operand 统一用空格分隔格式输出。
fn format_operands_compact(operands: &RawInstrOperands) -> String {
    match operands {
        RawInstrOperands::Lua51(op) => format_lua51_operands(op),
        RawInstrOperands::Lua52(op) => format_lua52_operands(op),
        RawInstrOperands::Lua53(op) => format_lua53_operands(op),
        RawInstrOperands::Lua54(op) => format_lua54_operands(op),
        RawInstrOperands::Lua55(op) => format_lua55_operands(op),
        RawInstrOperands::LuaJit(op) => format_luajit_operands(op),
        RawInstrOperands::Luau(op) => format_luau_operands(op),
    }
}

fn format_lua51_operands(op: &Lua51Operands) -> String {
    match op {
        Lua51Operands::A { a } => format!("{a}"),
        Lua51Operands::AB { a, b } => format!("{a} {b}"),
        Lua51Operands::AC { a, c } => format!("{a} {c}"),
        Lua51Operands::ABC { a, b, c } => format!("{a} {b} {c}"),
        Lua51Operands::ABx { a, bx } => format!("{a} {bx}"),
        Lua51Operands::AsBx { a, sbx } => format!("{a} {sbx}"),
    }
}

fn format_lua52_operands(op: &Lua52Operands) -> String {
    match op {
        Lua52Operands::A { a } => format!("{a}"),
        Lua52Operands::AB { a, b } => format!("{a} {b}"),
        Lua52Operands::AC { a, c } => format!("{a} {c}"),
        Lua52Operands::ABC { a, b, c } => format!("{a} {b} {c}"),
        Lua52Operands::ABx { a, bx } => format!("{a} {bx}"),
        Lua52Operands::AsBx { a, sbx } => format!("{a} {sbx}"),
        Lua52Operands::Ax { ax } => format!("{ax}"),
    }
}

fn format_lua53_operands(op: &Lua53Operands) -> String {
    match op {
        Lua53Operands::A { a } => format!("{a}"),
        Lua53Operands::AB { a, b } => format!("{a} {b}"),
        Lua53Operands::AC { a, c } => format!("{a} {c}"),
        Lua53Operands::ABC { a, b, c } => format!("{a} {b} {c}"),
        Lua53Operands::ABx { a, bx } => format!("{a} {bx}"),
        Lua53Operands::AsBx { a, sbx } => format!("{a} {sbx}"),
        Lua53Operands::Ax { ax } => format!("{ax}"),
    }
}

fn format_lua54_operands(op: &Lua54Operands) -> String {
    match op {
        Lua54Operands::None => String::new(),
        Lua54Operands::A { a } => format!("{a}"),
        Lua54Operands::Ak { a, k } => format!("{a} k={}", u8::from(*k)),
        Lua54Operands::AB { a, b } => format!("{a} {b}"),
        Lua54Operands::AC { a, c } => format!("{a} {c}"),
        Lua54Operands::ABk { a, b, k } => format!("{a} {b} k={}", u8::from(*k)),
        Lua54Operands::ABCk { a, b, c, k } => format!("{a} {b} {c} k={}", u8::from(*k)),
        Lua54Operands::ABx { a, bx } => format!("{a} {bx}"),
        Lua54Operands::AsBx { a, sbx } => format!("{a} {sbx}"),
        Lua54Operands::AsJ { sj } => format!("{sj}"),
        Lua54Operands::Ax { ax } => format!("{ax}"),
        Lua54Operands::ABsCk { a, b, sc, k } => format!("{a} {b} {sc} k={}", u8::from(*k)),
        Lua54Operands::AsBCk { a, sb, c, k } => format!("{a} {sb} {c} k={}", u8::from(*k)),
    }
}

fn format_lua55_operands(op: &Lua55Operands) -> String {
    match op {
        Lua55Operands::None => String::new(),
        Lua55Operands::A { a } => format!("{a}"),
        Lua55Operands::Ak { a, k } => format!("{a} k={}", u8::from(*k)),
        Lua55Operands::AB { a, b } => format!("{a} {b}"),
        Lua55Operands::AC { a, c } => format!("{a} {c}"),
        Lua55Operands::ABC { a, b, c } => format!("{a} {b} {c}"),
        Lua55Operands::ABk { a, b, k } => format!("{a} {b} k={}", u8::from(*k)),
        Lua55Operands::ABCk { a, b, c, k } => format!("{a} {b} {c} k={}", u8::from(*k)),
        Lua55Operands::ABx { a, bx } => format!("{a} {bx}"),
        Lua55Operands::AsBx { a, sbx } => format!("{a} {sbx}"),
        Lua55Operands::AsJ { sj } => format!("{sj}"),
        Lua55Operands::Ax { ax } => format!("{ax}"),
        Lua55Operands::ABsCk { a, b, sc, k } => format!("{a} {b} {sc} k={}", u8::from(*k)),
        Lua55Operands::AsBCk { a, sb, c, k } => format!("{a} {sb} {c} k={}", u8::from(*k)),
        Lua55Operands::AvBCk { a, vb, vc, k } => format!("{a} {vb} {vc} k={}", u8::from(*k)),
    }
}

fn format_luajit_operands(op: &LuaJitOperands) -> String {
    match op {
        LuaJitOperands::A { a } => format!("{a}"),
        LuaJitOperands::AD { a, d } => format!("{a} {d}"),
        LuaJitOperands::ABC { a, b, c } => format!("{a} {b} {c}"),
    }
}

fn format_luau_operands(op: &LuauOperands) -> String {
    match op {
        LuauOperands::None => String::new(),
        LuauOperands::A { a } => format!("{a}"),
        LuauOperands::AB { a, b } => format!("{a} {b}"),
        LuauOperands::AC { a, c } => format!("{a} {c}"),
        LuauOperands::ABC { a, b, c } => format!("{a} {b} {c}"),
        LuauOperands::AD { a, d } => format!("{a} {d}"),
        LuauOperands::E { e } => format!("{e}"),
    }
}

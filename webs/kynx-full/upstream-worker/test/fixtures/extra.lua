local up = 0
local function counter() up += 1 return up end
local t = {x = 1, y = 2, [3] = "z"}
for k, v in pairs(t) do print(k, v) end
for i = 10, 1, -2 do counter() end
repeat up -= 1 until up < 0
local s = "a" .. tostring(up) .. "b"
local f = function(...) return select("#", ...), ... end
print(s, f(1, 2, 3), Vector3.new(1, 2, 3), 1e300, nil, true)

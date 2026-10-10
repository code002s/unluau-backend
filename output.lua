-- dialect: luau
-- encoding: auto
-- decompiled by unluac-rs (https://github.com/x3zvawq/unluac-rs)

local r0_0 = game:GetService("Players")

local function r0_1(p1_0, p1_1) -- proto#1 params=2 locals=7 upvalues=0 vararg=false lines=2-2
    local r1_0 = 0
    for r1_1 = 1, p1_1 do
        if r1_1 % 2 == 0 then
            continue
        end
        r1_0 = r1_0 + r1_1
    end
    return (("%*:%*"):format(p1_0.Name, r1_0))
end

r0_0.PlayerAdded:Connect(function(p2_0) -- proto#2 params=1 locals=0 upvalues=1 vararg=false lines=10-10
    print(r0_1(p2_0, 10))
end)
local r0_2 = Vector3.new(1, 2, 3)
r0_0 = r0_2
r0_2 = { a = 1, b = 0 }
r0_2.b = { 2, 3 }
while true do
    local r0_3 = #r0_2.b
    if not (0 < r0_3) then
        break
    end
    table.remove(r0_2.b)
end
print(r0_0, r0_2)

local Players = game:GetService("Players")
local function greet(player: Player, n: number): string
	local total = 0
	for i = 1, n do
		if i % 2 == 0 then continue end
		total += i
	end
	return `{player.Name}:{total}`
end
Players.PlayerAdded:Connect(function(p)
	print(greet(p, 10))
end)
local v = Vector3.new(1, 2, 3)
local t = {a = 1, b = {2, 3}}
while #t.b > 0 do table.remove(t.b) end
print(v, t)
